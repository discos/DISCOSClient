import json
import unittest
import time
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
        self.socket.bind(f'tcp://127.0.0.1:{self.PORT}')
        messages_dir = Path(__file__).resolve().parent
        message_files = messages_dir.glob("messages/*.json")
        self.messages = {}
        for message in message_files:
            with open(message, "r", encoding="utf-8") as f:
                topic_name = message.stem
                self.messages[topic_name] = json.dumps(
                    json.load(f),
                    separators=(",", ":")
                )
        self.t = Thread(target=self.publish, daemon=True)
        self.event = Event()
        self.t.start()

    def publish(self):
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        while not self.event.is_set():
            events = dict(poller.poll(10))
            if self.socket in events:
                event = self.socket.recv()
                if event[0] == 1:
                    topic = event[1:].decode()
                    if "_" in topic:
                        t = topic.partition("_")[-1]
                        self.socket.send_string(f"{topic} {self.messages[t]}")
            for topic, payload in self.messages.items():
                self.socket.send_string(f'{topic} {payload}')

    def close(self):
        self.event.set()
        self.t.join()
        self.socket.close()
        self.context.term()


class TestBaseClient(unittest.TestCase):

    def test_no_topics(self):
        DISCOSClient(address="127.0.0.1")

    def test_unknown_topic(self):
        with self.assertRaises(ValueError) as ex:
            DISCOSClient("foo", address="127.0.0.1")
        self.assertTrue(
            "Topic 'foo' is not known" in ex.exception.args[0]
        )
        with self.assertRaises(ValueError) as ex:
            DISCOSClient("foo", "bar", address="127.0.0.1")
        self.assertTrue(
            "Topics 'foo' and 'bar' are not known" in ex.exception.args[0]
        )

    def test_repr(self):
        client = DISCOSClient(address="127.0.0.1")
        self.assertEqual(
            repr(client),
            "<DISCOSClient({})>"
        )

    def test_str(self):
        client = DISCOSClient(address="127.0.0.1")
        self.assertEqual(
            str(client),
            "{}"
        )

    def test_format(self):
        client = DISCOSClient(address="127.0.0.1")
        self.assertEqual(
            f"{client:}",
            "{}"
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
        b = {"a": 1.234, "b": "b"}
        ns = DISCOSNamespace(**b)
        a = {"antenna": b}
        client.antenna = ns
        self.assertEqual(
            f"{client:c}",
            json.dumps(a, separators=(",", ":"))
        )
        with self.assertRaises(ValueError) as ex:
            b = f"{client:3c}"
        self.assertEqual(
            str(ex.exception),
            "Compact format 'c' does not accept any parameter"
        )
        self.assertEqual(
            f"{client:i}",
            json.dumps(a, indent=2)
        )
        for indent in range(1, 10):
            self.assertEqual(
                f"{client:{indent}i}",
                json.dumps(a, indent=indent)
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


class TestSyncClient(unittest.TestCase):

    def test_sync_client(self):
        pub = TestPublisher()
        time.sleep(1)
        client = DISCOSClient("antenna", address="127.0.0.1")
        antenna = client.get("antenna", wait=True)
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
        pub.close()


class TestAsyncClient(unittest.IsolatedAsyncioTestCase):

    async def test_async_client(self):
        pub = TestPublisher()
        time.sleep(1)
        client = DISCOSClient(
            "antenna",
            address="127.0.0.1",
            asynchronous=True
        )
        antenna = await client.get("antenna", wait=True)
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
        pub.close()


if __name__ == '__main__':
    unittest.main()
