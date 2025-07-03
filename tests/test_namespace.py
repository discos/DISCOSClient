import unittest
import json
from copy import deepcopy
from discos_client.namespace import DISCOSNamespace


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
        self.assertEqual(str(ns), json.dumps(d, indent=2))
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

    def test_deepcopy(self):
        d = {"a": {"b": "a"}}
        ns = DISCOSNamespace(**d)
        ns2 = deepcopy(ns)
        self.assertFalse(ns2 is ns)

    def test_format(self):
        a = 1.234
        ns = DISCOSNamespace(value=a)
        self.assertEqual(f"{ns:.3f}", f"{a:.3f}")
        b = {"a": a, "enum": ["a", "b"]}
        ns = DISCOSNamespace(**b)
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:.3f}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '.3f' for DISCOSNamespace"
        )
        self.assertEqual(
            f"{ns:c}",
            json.dumps(b, separators=(",", ":"))
        )
        with self.assertRaises(ValueError) as ex:
            b = f"{ns:3c}"
        self.assertEqual(
            str(ex.exception),
            "Compact format 'c' does not accept any parameter"
        )
        self.assertEqual(
            f"{ns:i}",
            json.dumps(b, indent=2)
        )
        for indent in range(1, 10):
            self.assertEqual(
                f"{ns:{indent}i}",
                json.dumps(b, indent=indent)
            )
        with self.assertRaises(ValueError) as ex:
            b = f"{ns:0i}"
        self.assertEqual(
            str(ex.exception),
            "Indentation must be a positive integer"
        )
        with self.assertRaises(ValueError) as ex:
            b = f"{ns:ai}"
        self.assertEqual(
            str(ex.exception),
            "Invalid indent in format spec: 'a'"
        )
        self.assertEqual(f"{ns:}", str(ns))
        b = {"a": a, "b": ["a", "b"]}
        ns = DISCOSNamespace(**b)
        b2 = {"a": a, "b": {"items": ["a", "b"]}}
        self.assertEqual(
            f"{ns:i}",
            json.dumps(b2, indent=2)
        )

    def test_op(self):
        a = 2
        ns = DISCOSNamespace(value=a)
        self.assertEqual(ns + 2, 4)
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


if __name__ == '__main__':
    unittest.main()
