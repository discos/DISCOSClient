import json
import unittest
import time
import re
import asyncio
import sys
from unittest.mock import patch
from pathlib import Path
from threading import Thread, Event
import zmq
from zmq.auth import load_certificate
from zmq.auth.thread import ThreadAuthenticator
from discos_client.client import DISCOSClient, \
    SRTClient, MedicinaClient, NotoClient, \
    DEFAULT_SUB_PORT, DEFAULT_REQ_PORT
from discos_client.namespace import DISCOSNamespace


if sys.platform == "win32":
    # pylint: disable=deprecated-class
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

keys_path = Path(__file__).resolve().parent / "test_keys"
dummy_public, dummy_secret = load_certificate(
    keys_path / "dummy.key_secret"
)


class TestPublisher:

    def __init__(self, telescope=None, router=False):
        self.context = zmq.Context()
        self.pub = self.context.socket(zmq.XPUB)
        self.pub.setsockopt(zmq.LINGER, 0)
        self.pub.setsockopt(zmq.SNDHWM, 10)
        self.router = self.context.socket(zmq.ROUTER)
        self.router.curve_publickey = dummy_public
        self.router.curve_secretkey = dummy_secret
        self.router.curve_server = True
        self.auth = ThreadAuthenticator(self.context)
        self.auth.configure_curve(domain="*", location=keys_path)
        # This loop is necessary to wait for the client to close between tests
        while True:
            try:
                self.pub.bind(f"tcp://127.0.0.1:{DEFAULT_SUB_PORT}")
                break
            except zmq.ZMQError:
                continue
        if router:
            while True:
                try:
                    self.auth.start()
                    break
                except zmq.ZMQError:
                    continue
            while True:
                try:
                    self.router.bind(f"tcp://127.0.0.1:{DEFAULT_REQ_PORT}")
                    break
                except zmq.ZMQError:
                    continue
        self.poller = zmq.Poller()
        self.poller.register(self.pub, zmq.POLLIN)
        self.poller.register(self.router, zmq.POLLIN)
        messages_dir = Path(__file__).resolve().parent / "messages"
        message_files = list(messages_dir.glob("common/*.json"))
        if telescope:
            message_files += list(
                messages_dir.glob(f"{telescope.lower()}/*.json")
            )
        self.messages = {}
        for message in message_files:
            with open(message, "r", encoding="utf-8") as f:
                topic_name = message.stem
                self.messages[topic_name] = json.load(f)
        self.timestamps = []

        def recurse(obj):
            if isinstance(obj, dict):
                if "unix_time" in obj:
                    self.timestamps.append(obj)
                for v in obj.values():
                    recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)
        for payload in self.messages.values():
            recurse(payload)
        self.t = Thread(target=self.loop)
        self.event = Event()
        self.t.start()

    def __enter__(self):
        return self

    def _handle_events(self):
        zmq_events = {}
        try:
            zmq_events = dict(self.poller.poll(timeout=200))
        except zmq.ZMQError:
            return

        if self.pub in zmq_events:
            event = self.pub.recv(flags=zmq.DONTWAIT)
            op = event[0]
            topic = event[1:].decode(errors="ignore")
            if op == 1 and re.match(r"^[0-9A-Za-z]{4}_.+$", topic):
                t = topic.split("_", 1)[1]
                if t in self.messages:
                    message = json.dumps(
                        self.messages[t],
                        separators=(",", ":")
                    ).encode("utf-8")
                    self.pub.send_multipart([
                        topic.encode("ascii"),
                        message
                    ])
                else:
                    subparts = {}
                    for key, val in self.messages.items():
                        if key.startswith(f"{t}."):
                            subkey = key[len(t) + 1:]
                            subparts[subkey] = val
                    if subparts:
                        message = json.dumps(
                            subparts,
                            separators=(",", ":")
                        ).encode("utf-8")
                        self.pub.send_multipart([
                            topic.encode("ascii"), message
                        ])

        if self.router in zmq_events:
            req = self.router.recv_multipart(copy=False)
            routing_id, sep, payload = (req + [None])[:3]  # noqa
            payload = json.loads(payload.bytes)
            command = payload["command"]
            if command == "disconnect":
                # We are testing how the client handles server disconnection
                self.router.close()
            else:
                answer = {
                    "executed": True,
                    "command": payload["command"]
                }
                self.router.send_multipart([
                    routing_id,
                    b"",
                    json.dumps(answer, separators=(",", ":")).encode()
                ])

    def _send_periodic_messages(self):
        for timestamp in self.timestamps:
            timestamp["unix_time"] = time.time()
        for topic, payload in self.messages.items():
            if "." in topic:
                topic, obj = topic.split(".", 1)
                payload = {obj: payload}
            payload = json.dumps(
                payload,
                separators=(",", ":")
            ).encode("utf-8")
            self.pub.send_multipart([
                topic.encode("ascii"),
                payload
            ])

    def loop(self):
        while not self.event.is_set():
            self._handle_events()
            self._send_periodic_messages()
            time.sleep(0.1)

    def __exit__(self, exc_type, exc_value, traceback):
        self.event.set()
        self.t.join()
        self.pub.close()
        self.router.close()
        self.auth.stop()
        self.context.term()


class TestDISCOSClient(unittest.TestCase):

    def test_no_topics(self):
        DISCOSClient(
            address="127.0.0.1",
            sub_port=DEFAULT_SUB_PORT,
            telescope="SRT"
        )

    def test_unknown_telescope(self):
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                telescope="Unknown"
            )
        self.assertEqual(
            "Unknown telescope: 'Unknown'",
            ex.exception.args[0]
        )

    def test_unknown_topic(self):
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                "foo",
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT
            )
        self.assertTrue(
            "Topic 'foo' is not known" in ex.exception.args[0]
        )
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                "foo", "bar",
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
            )
        self.assertTrue(
            "Topics 'foo' and 'bar' are not known" in ex.exception.args[0]
        )

    def test_repr(self):
        client = DISCOSClient(
            address="127.0.0.1",
            sub_port=DEFAULT_SUB_PORT
        )
        self.assertTrue(
            repr(client).startswith("<DISCOSClient({") and
            repr(client).endswith("})>")
        )

    def test_str(self):
        client = DISCOSClient(
            address="127.0.0.1",
            sub_port=DEFAULT_SUB_PORT
        )
        self.assertTrue(
            str(client).startswith("{") and
            str(client).endswith("}")
        )

    def test_format(self):
        client = DISCOSClient(
            address="127.0.0.1",
            sub_port=DEFAULT_SUB_PORT
        )
        self.assertTrue(
            f"{client:}".startswith("{") and
            f"{client:}".endswith("}")
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:u}"
        self.assertEqual(
            ex.exception.args[0],
            "Unknown format code 'u' for DISCOSClient"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:.3e}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '.3e' for DISCOSClient"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:.3m}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '.3m' for DISCOSClient"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:em}"
        self.assertEqual(
            str(ex.exception),
            "Format specifier cannot contain both 'e' and 'm'."
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:0i}"
        self.assertEqual(
            str(ex.exception),
            "Indentation must be a positive integer"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:ai}"
        self.assertEqual(
            str(ex.exception),
            "Invalid indent in format spec: 'a'"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:3c}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '3c' for DISCOSClient"
        )
        self.assertNotIn("\": ", f"{client:t}")

    def test_bind(self):
        with TestPublisher("SRT"):
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT
            )
            s = set()
            called = set()
            s.add(id(client.antenna.timestamp.unix_time))
            s.add(id(client.antenna))

            def callback(value):
                called.add(id(value))

            client.antenna.timestamp.unix_time.bind(callback)
            client.antenna.bind(callback)

            start = time.time()
            while len(called) < 2 and (time.time() - start) < 60:
                time.sleep(0.1)
            self.assertEqual(s, called)
            client.antenna.timestamp.unix_time.unbind(callback)
            client.antenna.unbind(callback, str)  # Never used predicate
            client.antenna.unbind(callback)
            client.antenna.unbind(int)  # Never bound callback
            client.antenna.unbind(None)  # Unbind all callbacks

            def custom_predicate(_):
                return True

            client.antenna.bind(callback, predicate=custom_predicate)
            client.antenna.unbind(callback, predicate=custom_predicate)

    def test_wait(self):
        with TestPublisher():
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT
            )
            unix_time = client.antenna.timestamp.unix_time.copy()
            antenna = client.antenna.copy()
            self.assertNotEqual(
                unix_time,
                client.antenna.timestamp.unix_time.wait(timeout=10)
            )
            self.assertNotEqual(
                antenna,
                client.antenna.wait(timeout=5)
            )

    def test_unwrap(self):
        with TestPublisher("SRT"):
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT
            )

            received_values = []

            def callback(value):
                received_values.append(value)

            client.antenna.timestamp.unix_time.bind(
                callback,
                unwrap=True
            )

            start = time.time()
            while not received_values and (time.time() - start) < 10:
                time.sleep(0.1)

            self.assertTrue(len(received_values) > 0)

            first_val = received_values[0]
            self.assertNotIsInstance(first_val, DISCOSNamespace)
            self.assertIsInstance(first_val, float)

            client.antenna.timestamp.unix_time.unbind(callback)

            new_val = client.antenna.timestamp.unix_time.wait(
                timeout=10,
                unwrap=True
            )

            self.assertNotIsInstance(new_val, DISCOSNamespace)
            self.assertIsInstance(new_val, float)

    @patch("discos_client.utils.load_certificate")
    def test_command(self, mock_load_cert):
        mock_load_cert.return_value = (dummy_public, dummy_secret)
        with TestPublisher(router=True):
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                telescope="SRT",
                identity="identity"
            )
            self.assertTrue(hasattr(client, "command"))
            answer = client.command("dummy")
            self.assertTrue(answer.executed)

    @patch("discos_client.utils.load_certificate")
    def test_command_with_args(self, mock_load_cert):
        mock_load_cert.return_value = (dummy_public, dummy_secret)
        with TestPublisher(router=True):
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                telescope="SRT",
                identity="identity"
            )
            self.assertTrue(hasattr(client, "command"))
            answer = client.command("dummy", 1, 2, 3)
            self.assertTrue(answer.executed)

    @patch("discos_client.utils.load_certificate")
    def test_command_unreachable(self, mock_load_cert):
        mock_load_cert.return_value = (dummy_public, dummy_secret)
        with TestPublisher():
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                telescope="SRT",
                identity="identity"
            )
            self.assertTrue(hasattr(client, "command"))
            self.assertFalse(client.command("dummy").executed)

    def test_command_not_present(self):
        client = DISCOSClient(
            address="127.0.0.1",
            sub_port=DEFAULT_SUB_PORT
        )
        self.assertFalse(hasattr(client, "command"))

    @patch("discos_client.utils.load_certificate")
    def test_command_unknown_keys(self, mock_load_cert):
        mock_load_cert.side_effect = OSError
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                telescope="SRT",
                identity="dummy"
            )
        self.assertIn("Unknown or invalid identity", str(ex.exception))

    @patch("discos_client.utils.load_certificate")
    def test_command_disconnect_after_send(self, mock_load_cert):
        mock_load_cert.return_value = (dummy_public, dummy_secret)
        with TestPublisher(router=True):
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                telescope="SRT",
                identity="identity"
            )
            self.assertTrue(hasattr(client, "command"))
            answer = client.command("disconnect")
            self.assertFalse(answer.executed)

    @patch("discos_client.utils.load_certificate")
    def test_command_with_server_public_key_file(self, mock_load_cert):
        mock_load_cert.return_value = (dummy_public, dummy_secret)
        with TestPublisher(router=True):
            client = DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                telescope="SRT",
                identity="identity",
                server_public_key_file="/tmp/server.key",
            )
            self.assertTrue(hasattr(client, "command"))
            answer = client.command("dummy")
            self.assertTrue(answer.executed)

    @patch("discos_client.utils.load_certificate")
    def test_command_without_telescope_or_server_public_key_file(
        self,
        mock_load_cert
    ):
        mock_load_cert.return_value = (dummy_public, dummy_secret)
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                address="127.0.0.1",
                sub_port=DEFAULT_SUB_PORT,
                req_port=DEFAULT_REQ_PORT,
                identity="identity",
            )
        self.assertIn(
            "Either 'telescope' or 'server_public_key_file' must be provided",
            str(ex.exception)
        )


class TestTelescopeClients(unittest.TestCase):

    def test_srt_client(self):
        _ = SRTClient()

    def test_medicina_client(self):
        _ = MedicinaClient()

    def test_noto_client(self):
        _ = NotoClient()


if __name__ == '__main__':
    unittest.main()
