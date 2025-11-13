import unittest
import json
from pathlib import Path
from copy import deepcopy
from discos_client.namespace import DISCOSNamespace


# pylint: disable=too-many-public-methods
class TestDISCOSNamespace(unittest.TestCase):

    def test_assignment(self):
        ns = DISCOSNamespace()
        with self.assertRaises(TypeError) as ex:
            ns.attribute = "a"
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace is read-only and does "
            "not allow attribute assignment"
        )

    def test_deletion(self):
        ns = DISCOSNamespace(description="a")
        with self.assertRaises(TypeError) as ex:
            del ns.a
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace is read-only and does "
            "not allow attribute deletion"
        )

    def test_repr(self):
        a = {"a": {"b": {"value": ["a", "b"]}}}
        ns = DISCOSNamespace(**a)
        self.assertEqual(
            repr(ns),
            "<DISCOSNamespace({'a': {'b': ['a', 'b']}})>"
        )
        ns = DISCOSNamespace(value="a")
        self.assertEqual(repr(ns), "'a'")

    def test_str(self):
        a = "a"
        d = {"a": a}
        ns = DISCOSNamespace(**d)
        self.assertEqual(str(ns), json.dumps(d))
        d = {"value": a}
        ns = DISCOSNamespace(**d)
        self.assertEqual(str(ns), f"{a}")

    def test_int(self):
        a = 1
        ns = DISCOSNamespace(value=a)
        self.assertEqual(int(ns), a)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            int(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be converted to int"
        )

    def test_float(self):
        a = 1.0
        ns = DISCOSNamespace(value=a)
        self.assertEqual(float(ns), a)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            float(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be converted to float"
        )

    def test_neg(self):
        a = 1.0
        ns = DISCOSNamespace(value=a)
        b = -ns
        self.assertEqual(b, -a)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            b = -ns
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be negated"
        )

    def test_abs(self):
        ns = DISCOSNamespace(value=-1.0)
        b = abs(ns)
        self.assertEqual(b, 1.0)
        ns = DISCOSNamespace(a="foo")
        with self.assertRaises(TypeError) as ex:
            _ = abs(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object is not a numeric type."
        )

    def test_round(self):
        ns = DISCOSNamespace(value=0.123456)
        b = round(ns, 3)
        self.assertEqual(b, 0.123)
        ns = DISCOSNamespace(a="foo")
        with self.assertRaises(TypeError) as ex:
            _ = round(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be rounded."
        )

    def test_bool(self):
        a = True
        ns = DISCOSNamespace(value=a)
        self.assertTrue(ns)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            bool(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be converted to bool"
        )

    def test_getitem(self):
        a = [1, 2]
        ns = DISCOSNamespace(value=a)
        self.assertEqual(ns[0], 1)
        self.assertEqual(ns[1], 2)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            _ = ns[0]
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object is not subscriptable"
        )

    def test_len(self):
        a = [1, 2]
        ns = DISCOSNamespace(value=a)
        self.assertEqual(len(ns), len(a))
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            len(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object has no length"
        )

    def test_iter(self):
        a = [1, 2]
        ns = DISCOSNamespace(value=a)
        self.assertEqual(list(ns), a)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            list(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object is not iterable"
        )

    def test_copy(self):
        d = {"a": {"b": "a"}}
        ns = DISCOSNamespace(**d)
        ns2 = ns.copy()
        self.assertFalse(ns2 is ns)

    def test_deepcopy(self):
        d = {"a": {"b": {"value": ["a", "b"]}}}
        ns = DISCOSNamespace(**d)
        ns2 = deepcopy(ns)
        self.assertFalse(ns2 is ns)

    def test_format(self):
        a = 1.234
        ns = DISCOSNamespace(value=a)
        self.assertEqual(f"{ns:.3f}", f"{a:.3f}")
        b = {"a": {"title": "a", "value": a}, "enum": ["a", "b"]}
        ns = DISCOSNamespace(**b)
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:.3f}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '.3f' for DISCOSNamespace"
        )
        self.assertEqual(
            f"{ns:c}",
            json.dumps({"a": a}, separators=(",", ":"))
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:3c}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '3c' for DISCOSNamespace"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:fm}"
        self.assertEqual(
            str(ex.exception),
            "Format specifier cannot contain both 'f' and 'm'."
        )
        self.assertEqual(
            f"{ns:i}",
            json.dumps({"a": a}, indent=2)
        )
        self.assertEqual(
            f"{ns:f}",
            json.dumps(b)
        )
        b_ = deepcopy(b)
        b_["a"].pop("value")
        self.assertEqual(
            f"{ns:m}",
            json.dumps(b_)
        )
        for indent in range(1, 10):
            self.assertEqual(
                f"{ns:{indent}i}",
                json.dumps({"a": a}, indent=indent)
            )
            self.assertEqual(
                f"{ns:f{indent}i}",
                json.dumps(b, indent=indent)
            )
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:0i}"
        self.assertEqual(
            str(ex.exception),
            "Indentation must be a positive integer"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:ai}"
        self.assertEqual(
            str(ex.exception),
            "Invalid indent in format spec: 'a'"
        )

        messages_dir = Path(__file__).resolve().parent
        message_files = messages_dir.glob("messages/*.json")
        for message in message_files:
            with open(message, "r", encoding="utf-8") as f:
                d = json.load(f)
                ns = DISCOSNamespace(**d)
                self.assertEqual(f"{ns}", json.dumps(d))
                _ = f"{ns:f}"

    def test_op(self):
        a = 2
        ns = DISCOSNamespace(value=a)
        self.assertEqual(ns + 2, 4)
        self.assertEqual(2 + ns, 4)
        ns = DISCOSNamespace(a=a)
        with self.assertRaises(TypeError) as ex:
            _ = ns + 2
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace supports operations "
            "only when holding a primitive value"
        )

    def test_ilshift(self):
        d = {"value": "a", "a": {"value": "a"}, "_a": "a"}
        d2 = {"value": "b", "a": {"value": "b"}, "_a": "b"}
        ns = DISCOSNamespace(**d)
        ns2 = DISCOSNamespace(**d2)
        self.assertEqual(ns, "a")
        self.assertEqual(ns.a, "a")
        self.assertEqual(ns._a, "a")  # noqa
        ns <<= ns2
        self.assertEqual(ns, "b")
        self.assertEqual(ns.a, "b")
        self.assertEqual(ns._a, "a")  # noqa
        self.assertFalse(ns is ns2)
        ns <<= ns  # Should return immediately and do nothing

    def test_comparison(self):
        a = 2
        ns = DISCOSNamespace(value=a)
        ns2 = DISCOSNamespace(value=a)
        self.assertEqual(ns, a)
        self.assertNotEqual(ns, a + 1)
        self.assertFalse(ns < ns2)
        self.assertFalse(ns > ns2)

    def test_dir(self):
        ns = DISCOSNamespace(value="foo", title="title")
        attributes = dir(ns)
        self.assertIn("upper", attributes)
        self.assertIn("title", attributes)
        self.assertIn("startswith", attributes)
        ns = DISCOSNamespace(title="title")
        attributes = dir(ns)
        self.assertNotIn("get_value", attributes)
        ns = DISCOSNamespace(value=ns)
        attributes = dir(ns)
        self.assertNotIn("get_value", attributes)

    def test_getattr(self):
        ns = DISCOSNamespace(value="foo")
        self.assertEqual(ns.upper(), "foo".upper())
        with self.assertRaises(AttributeError) as ex:
            _ = ns.unknown
        self.assertEqual(
            str(ex.exception),
            "'DISCOSNamespace' object has no attribute 'unknown'"
        )

    def test_get_value(self):
        ns = DISCOSNamespace(value="foo")
        self.assertIsInstance(ns.get_value(), str)
        ns = DISCOSNamespace(value=ns)
        with self.assertRaises(AttributeError) as ex:
            _ = ns.get_value()
        self.assertEqual(
            str(ex.exception),
            "'DISCOSNamespace' object has no attribute 'get_value'"
        )
        ns = DISCOSNamespace(title="foo")
        with self.assertRaises(AttributeError) as ex:
            _ = ns.get_value()
        self.assertEqual(
            str(ex.exception),
            "'DISCOSNamespace' object has no attribute 'get_value'"
        )


if __name__ == '__main__':
    unittest.main()
