import json
import unittest
import time
import re
from pathlib import Path
from threading import Thread, Event
import zmq
from discos_client import DISCOSClient
from discos_client.namespace import DISCOSNamespace


class TestPublisher:

    PORT = 16000

    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.XPUB)
        self.socket.setsockopt(zmq.SNDHWM, 2)
        self.socket.bind(f"tcp://127.0.0.1:{self.PORT}")
        messages_dir = Path(__file__).resolve().parent
        message_files = messages_dir.glob("messages/*.json")
        self.messages = {}
        for message in message_files:
            with open(message, "r", encoding="utf-8") as f:
                topic_name = message.stem
                self.messages[topic_name] = json.load(f)
        self.t = Thread(target=self.publish, daemon=True)
        self.event = Event()
        self.t.start()

    def __enter__(self):
        return self

    def _handle_subscription(self, poller):
        events = dict(poller.poll(100))
        if self.socket in events:
            event = self.socket.recv()
            if event[0] != 1:
                return
            topic = event[1:].decode()
            if re.match(r"^\d{3}_.+$", topic):
                *_, t = topic.partition("_")
                if t in self.messages:
                    message = json.dumps(
                        self.messages[t],
                        separators=(',', ':')
                    )
                    self.socket.send_string(
                        f"{topic} {message}"
                    )
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
                        )
                        self.socket.send_string(f"{topic} {message}")

    def _send_periodic_messages(self):
        for topic, payload in self.messages.items():
            payload["timestamp"]["unix_time"] = time.time()
            if "." in topic:
                topic, obj = topic.split(".", 1)
                payload = {obj: payload}
            payload = json.dumps(
                payload,
                separators=(",", ":")
            )
            self.socket.send_string(f"{topic} {payload}")

    def publish(self):
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        while not self.event.is_set():
            self._handle_subscription(poller)
            self._send_periodic_messages()
            time.sleep(0.1)

    def __exit__(self, exc_type, exc_value, traceback):
        self.event.set()
        self.t.join()
        self.socket.close()
        self.context.term()


class TestBaseClient(unittest.TestCase):

    def test_no_topics(self):
        DISCOSClient(address="127.0.0.1", port=16000, telescope="SRT")

    def test_unknown_topic(self):
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                "foo",
                address="127.0.0.1",
                port=16000
            )
        self.assertTrue(
            "Topic 'foo' is not known" in ex.exception.args[0]
        )
        with self.assertRaises(ValueError) as ex:
            DISCOSClient(
                "foo", "bar",
                address="127.0.0.1",
                port=16000,
            )
        self.assertTrue(
            "Topics 'foo' and 'bar' are not known" in ex.exception.args[0]
        )

    def test_repr(self):
        client = DISCOSClient(address="127.0.0.1", port=16000)
        self.assertTrue(
            repr(client).startswith("<DISCOSClient({") and
            repr(client).endswith("})>")
        )

    def test_str(self):
        client = DISCOSClient(address="127.0.0.1", port=16000)
        self.assertTrue(
            str(client).startswith("{") and str(client).endswith("}")
        )

    def test_format(self):
        client = DISCOSClient(address="127.0.0.1", port=16000)
        self.assertTrue(
            f"{client:}".startswith("{") and f"{client:}".endswith("}")
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:u}"
        self.assertEqual(
            ex.exception.args[0],
            "Unknown format code 'u' for DISCOSClient"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{client:.3f}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '.3f' for DISCOSClient"
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
        self.assertNotIn("\": ", f"{client:c}")

    def test_bind(self):
        with TestPublisher():
            client = DISCOSClient(address="127.0.0.1", port=16000)
            time.sleep(1)
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

    def test_wait(self):
        with TestPublisher():
            client = DISCOSClient(address="127.0.0.1", port=16000)
            time.sleep(1)
            unix_time = client.antenna.timestamp.unix_time.copy()
            antenna = client.antenna.copy()
            self.assertNotEqual(
                unix_time,
                client.antenna.timestamp.unix_time.wait(timeout=5)
            )
            self.assertNotEqual(
                antenna,
                client.antenna.wait(timeout=5)
            )


class TestSyncClient(unittest.TestCase):

    def test_sync_client(self):
        with TestPublisher():
            client = DISCOSClient(
                "antenna",
                address="127.0.0.1",
                port=16000,
                telescope="SRT"
            )
            time.sleep(1)
            antenna = client.get("antenna.timestamp", wait=True)
            self.assertIsInstance(antenna, DISCOSNamespace)
            antenna = client.get("antenna")
            self.assertIsInstance(antenna, DISCOSNamespace)
            with self.assertRaises(KeyError) as ex:
                client.get("unknown")
            self.assertEqual(
                ex.exception.args[0],
                "Unknown topic 'unknown'"
            )
            with self.assertRaises(KeyError) as ex:
                client.get("mount")
            self.assertEqual(
                ex.exception.args[0],
                "The client is not subscribed to 'mount'"
            )


class TestAsyncClient(unittest.IsolatedAsyncioTestCase):

    async def test_async_client(self):
        with TestPublisher():
            client = DISCOSClient(
                "antenna",
                address="127.0.0.1",
                port=16000,
                telescope="SRT",
                asynchronous=True
            )
            time.sleep(1)
            antenna = await client.get("antenna.timestamp", wait=True)
            self.assertIsInstance(antenna, DISCOSNamespace)
            antenna = await client.get("antenna")
            self.assertIsInstance(antenna, DISCOSNamespace)
            with self.assertRaises(KeyError) as ex:
                await client.get("unknown")
            self.assertEqual(
                ex.exception.args[0],
                "Unknown topic 'unknown'"
            )
            with self.assertRaises(KeyError) as ex:
                await client.get("mount")
            self.assertEqual(
                ex.exception.args[0],
                "The client is not subscribed to 'mount'"
            )


if __name__ == '__main__':
    unittest.main()
