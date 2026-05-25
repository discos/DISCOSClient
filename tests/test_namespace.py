import unittest
import re
from pathlib import Path
from copy import deepcopy
import orjson
from discos_client.namespace import DISCOSNamespace
from discos_client.namespace import _plain_merge


def _wire(parent, key, meta, reactive):
    """
    Build a DISCOSNamespace node at parent[key] and recursively wire children.
    No schema info available here, so children carry empty metadata.
    """
    ns = DISCOSNamespace(parent, key, meta, reactive)
    node = parent[key]
    if isinstance(node, dict):
        for k in node.keys():
            child = _wire(node, k, {}, reactive)
            ns._children[k] = child
    elif isinstance(node, list):
        for i, _ in enumerate(node):
            child = _wire(node, i, {}, reactive)
            ns._children[i] = child
    return ns


def _ns(data, meta=None, key="__root__", reactive=True):
    """
    Build a fully-wired DISCOSNamespace tree from plain Python *data*.

    *data* can be a dict, list, or any primitive.  *meta* sets schema
    metadata on the root node.  *key* is the root node's key (used by the
    ``'w'`` format specifier).
    """
    wrapper = {key: data}
    return _wire(wrapper, key, meta or {}, reactive)


def _ns_with_child_meta(data, root_meta=None, children_meta=None,
                        key="__root__", reactive=True):
    """
    Like ``_ns`` but also attaches per-child schema metadata.

    *children_meta* is ``{child_key: {meta_key: meta_value, ...}, ...}``.
    """
    wrapper = {key: data}
    ns = DISCOSNamespace(wrapper, key, root_meta or {}, reactive)
    children_meta = children_meta or {}
    if isinstance(data, dict):
        for k in data.keys():
            child = _wire(data, k, children_meta.get(k, {}), reactive)
            ns._children[k] = child
    return ns


# pylint: disable=too-many-public-methods
class TestDISCOSNamespace(unittest.TestCase):

    def test_assignment(self):
        ns = _ns({})
        with self.assertRaises(TypeError) as ex:
            ns.attribute = "a"
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace is read-only and does "
            "not allow attribute assignment"
        )

    def test_deletion(self):
        ns = _ns({}, meta={"description": "a"})
        with self.assertRaises(TypeError) as ex:
            del ns.a
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace is read-only and does "
            "not allow attribute deletion"
        )

    def test_repr(self):
        ns = _ns({"a": {"b": ["a", "b"]}})
        self.assertEqual(
            repr(ns),
            "<DISCOSNamespace({'a': {'b': ['a', 'b']}})>"
        )
        # Leaf node.
        ns = _ns("a")
        self.assertEqual(repr(ns), "'a'")

    def test_str(self):
        d = {"a": "a"}
        ns = _ns(d)
        self.assertEqual(
            str(ns),
            orjson.dumps(d, option=orjson.OPT_SORT_KEYS).decode()
        )
        ns = _ns("a")
        self.assertEqual(str(ns), "a")

    def test_int(self):
        a = 1
        ns = _ns(a)
        self.assertEqual(int(ns), a)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            int(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be converted to int"
        )

    def test_float(self):
        a = 1.0
        ns = _ns(a)
        self.assertEqual(float(ns), a)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            float(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be converted to float"
        )

    def test_neg(self):
        a = 1.0
        ns = _ns(a)
        b = -ns
        self.assertEqual(b, -a)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            b = -ns
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be negated"
        )

    def test_abs(self):
        ns = _ns(-1.0)
        b = abs(ns)
        self.assertEqual(b, 1.0)
        ns = _ns({"a": "foo"})
        with self.assertRaises(TypeError) as ex:
            _ = abs(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object is not a numeric type."
        )

    def test_round(self):
        ns = _ns(0.123456)
        b = round(ns, 3)
        self.assertEqual(b, 0.123)
        ns = _ns({"a": "foo"})
        with self.assertRaises(TypeError) as ex:
            _ = round(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be rounded."
        )

    def test_bool(self):
        a = True
        ns = _ns(a)
        self.assertTrue(ns)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            bool(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object cannot be converted to bool"
        )

    def test_getitem(self):
        a = [1, 2]
        ns = _ns(a)
        self.assertEqual(ns[0], 1)
        self.assertEqual(ns[1], 2)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            _ = ns[0]
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object is not subscriptable"
        )

    def test_len(self):
        a = [1, 2]
        ns = _ns(a)
        self.assertEqual(len(ns), len(a))
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            len(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object has no length"
        )

    def test_iter(self):
        a = [1, 2]
        ns = _ns(a)
        self.assertEqual(list(ns), a)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            list(ns)
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace object is not iterable"
        )

    def test_copy(self):
        ns = _ns({"a": {"b": "a"}})
        ns2 = ns.copy()
        self.assertFalse(ns2 is ns)

    def test_deepcopy(self):
        ns = _ns({"a": {"b": ["a", "b"]}})
        ns2 = deepcopy(ns)
        self.assertFalse(ns2 is ns)

    def test_format(self):
        a = 1.234

        ns = _ns(a)
        self.assertEqual(f"{ns:.3f}", f"{a:.3f}")

        ns = _ns_with_child_meta(
            {"a": a},
            root_meta={"enum": ["a", "b"]},
            children_meta={"a": {"title": "a"}},
        )
        b = {"a": {"title": "a", "value": a}, "enum": ["a", "b"]}

        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:.3f}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '.3f' for DISCOSNamespace"
        )
        self.assertEqual(
            f"{ns:t}",
            orjson.dumps({"a": a}, option=orjson.OPT_SORT_KEYS).decode()
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:3c}"
        self.assertEqual(
            str(ex.exception),
            "Unknown format code '3c' for DISCOSNamespace"
        )
        with self.assertRaises(ValueError) as ex:
            _ = f"{ns:em}"
        self.assertEqual(
            str(ex.exception),
            "Format specifier cannot contain both 'e' and 'm'."
        )
        self.assertEqual(
            f"{ns:i}",
            orjson.dumps(
                {"a": a},
                option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2
            ).decode()
        )
        self.assertEqual(
            f"{ns:e}",
            orjson.dumps(b, option=orjson.OPT_SORT_KEYS).decode()
        )
        b_ = deepcopy(b)
        b_["a"].pop("value")
        self.assertEqual(
            f"{ns:m}",
            orjson.dumps(b_, option=orjson.OPT_SORT_KEYS).decode()
        )

        messages_dir = Path(__file__).resolve().parent
        message_files = list(messages_dir.glob("messages/*.json"))
        for message in message_files:
            d = orjson.loads(Path(message).read_bytes())
            ns_msg = _ns(d)
            self.assertEqual(
                f"{ns_msg}",
                orjson.dumps(d, option=orjson.OPT_SORT_KEYS).decode()
            )

        ns_w = _ns({"b": 1.234}, key="a")
        self.assertEqual(
            f"{ns_w:w}",
            orjson.dumps(
                {"a": {"b": 1.234}},
                option=orjson.OPT_SORT_KEYS
            ).decode()
        )

    def test_op(self):
        a = 2
        ns = _ns(a)
        self.assertEqual(ns + 2, 4)
        self.assertEqual(2 + ns, 4)
        ns = _ns({"a": a})
        with self.assertRaises(TypeError) as ex:
            _ = ns + 2
        self.assertEqual(
            str(ex.exception),
            "DISCOSNamespace supports operations "
            "only when holding a primitive value"
        )

    def test_ilshift(self):
        ns = _ns({"a": "a", "b": {"c": "a"}})
        ns2 = _ns({"a": "b", "b": {"c": "b"}})

        self.assertEqual(ns.a, "a")
        self.assertEqual(ns.b.c, "a")

        ns <<= ns2

        self.assertEqual(ns.a, "b")
        self.assertEqual(ns.b.c, "b")
        self.assertFalse(ns is ns2)

        ns3 = ns.copy()
        ns <<= ns
        ns <<= ns3

        with self.assertRaises(TypeError) as ex:
            ns <<= b"a"
        self.assertEqual(
            str(ex.exception),
            "Unsupported operand type for <<=: 'DISCOSNamespace' and 'bytes'"
        )

    def test_comparison(self):
        a = 2
        ns = _ns(a)
        ns2 = _ns(a)
        ns3 = _ns({"a": a})
        self.assertEqual(ns, a)
        self.assertNotEqual(ns, a + 1)
        self.assertFalse(ns < ns2)
        self.assertFalse(ns > ns2)
        self.assertNotEqual(ns3, a)

    def test_dir(self):
        ns = _ns("foo", meta={"title": "title"})
        attributes = dir(ns)
        self.assertIn("upper", attributes)
        self.assertIn("title", attributes)
        self.assertIn("startswith", attributes)

        ns = _ns({}, meta={"title": "title"})
        attributes = dir(ns)
        self.assertNotIn("get_value", attributes)

    def test_getattr(self):
        ns = _ns("foo")
        self.assertEqual(ns.upper(), "foo".upper())
        with self.assertRaises(AttributeError) as ex:
            _ = ns.unknown
        self.assertEqual(
            str(ex.exception),
            "'DISCOSNamespace' object has no attribute 'unknown'"
        )

    def test_get_value(self):
        ns = _ns("foo")
        self.assertIsInstance(ns.get_value(), str)

        ns = _ns({"title": "foo"})
        with self.assertRaises(AttributeError) as ex:
            _ = ns.get_value()
        self.assertEqual(
            str(ex.exception),
            "'DISCOSNamespace' object has no attribute 'get_value'"
        )

        ns = _ns({}, meta={"title": "foo"})
        with self.assertRaises(AttributeError) as ex:
            _ = ns.get_value()
        self.assertEqual(
            str(ex.exception),
            "'DISCOSNamespace' object has no attribute 'get_value'"
        )

    def test_plain_merge(self):
        data = {"outer": {"inner": {"x": 1, "y": 2}}}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        outer_ns = DISCOSNamespace(data, "outer", {}, True)
        ns._children["outer"] = outer_ns
        ns <<= {"outer": {"inner": {"x": 99, "y": 100}}}
        self.assertEqual(data["outer"]["inner"]["x"], 99)
        self.assertEqual(data["outer"]["inner"]["y"], 100)

    def test_get_value_raises_on_dict(self):
        data = {"k": {"nested": 1}}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        object.__setattr__(ns, 'get_value', ns.__get_value__)
        with self.assertRaises(TypeError) as ex:
            ns.get_value()
        self.assertIn("does not hold a primitive value", str(ex.exception))

    def test_getattr_returns_schema_meta(self):
        ns = _ns(42, meta={"title": "My Field", "unit": "degrees"})
        self.assertEqual(ns.title, "My Field")
        self.assertEqual(ns.unit, "degrees")

    def test_value_comparison_type_error(self):
        ns1 = _ns({"a": 1})
        ns2 = _ns({"b": 2})
        result = ns1 < ns2
        self.assertFalse(result)

    def test_ilshift_list(self):
        ns = _ns([1, 2, 3])
        ns <<= [4, 5, 6]
        self.assertEqual(ns[0], 4)
        self.assertEqual(ns[1], 5)
        self.assertEqual(ns[2], 6)
        self.assertEqual(len(ns), 3)

    def test_ilshift_list_resize(self):
        ns = _ns([1, 2])
        ns <<= [10, 20, 30]
        self.assertEqual(len(ns), 3)
        self.assertEqual(ns[2], 30)

    def test_ilshift_primitive(self):
        ns = _ns(1)
        ns <<= 42
        self.assertEqual(ns, 42)
        ns <<= 42
        self.assertEqual(ns, 42)

    def test_ilshift_primitive_none(self):
        ns = _ns(1)
        ns <<= None
        node = ns._get_node()
        self.assertIsNone(node)

    def test_merge_dict_list_without_child(self):
        data = {"lst": [1, 2]}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        ns <<= {"lst": [9, 8, 7]}
        self.assertEqual(data["lst"], [9, 8, 7])

    def test_make_dynamic_child_no_match(self):
        ns = _ns({"existing": 1})
        result = ns._make_dynamic_child({"new_key": {"x": 1}}, "new_key")
        self.assertIsNone(result)

    def test_format_w_raises_without_key(self):
        wrapper = {None: {"a": 1}}
        ns = DISCOSNamespace(wrapper, None, {}, True)
        with self.assertRaises(ValueError) as ex:
            format(ns, "w")
        self.assertEqual(str(ex.exception), "Cannot wrap node without a key!")

    def test_format_full_dict_list_node(self):
        ns = _ns([1, 2, 3])
        result = orjson.loads(f"{ns:e}")
        self.assertIn("items", result)

    def test_meta_dict_array_node(self):
        ns = _ns([1, 2])
        object.__setattr__(
            ns,
            '_item_full_meta',
            {"title": "Item", "type": "number"}
        )
        result = orjson.loads(f"{ns:m}")
        self.assertIn("items", result)
        self.assertEqual(result["items"][0]["title"], "Item")

    def test_full_dict_classmethod(self):
        ns = _ns_with_child_meta(
            {"x": 1.0},
            children_meta={"x": {"title": "X", "unit": "m"}}
        )
        result = DISCOSNamespace.__full_dict__(ns)
        self.assertIn("x", result)

    def test_metadata_dict_classmethod(self):
        ns = _ns_with_child_meta(
            {"x": 1.0},
            root_meta={"title": "Root"},
            children_meta={"x": {"title": "X"}}
        )
        result = DISCOSNamespace.__metadata_dict__(ns)
        self.assertIn("title", result)
        self.assertNotIn("x", result.get("x", {}).get("value", {}))

    def test_update_list_item_changed(self):
        notified = []
        ns = _ns([10, 20, 30])
        for i in range(3):
            ns._children[i].bind(lambda v, i=i: notified.append(i))
        ns <<= [10, 99, 30]
        self.assertIn(1, notified)
        self.assertNotIn(0, notified)
        self.assertNotIn(2, notified)

    def test_plain_merge_changes_nested(self):
        data = {"outer": {"inner": {"x": 1}}}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        outer_ns = DISCOSNamespace(data, "outer", {}, True)
        ns._children["outer"] = outer_ns
        ns <<= {"outer": {"inner": {"x": 2}}}
        self.assertEqual(data["outer"]["inner"]["x"], 2)

    def test_update_list_replaces_non_list_node(self):
        wrapper = {"root": 42}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        ns <<= [1, 2, 3]
        self.assertEqual(ns._get_node(), [1, 2, 3])

    def test_update_list_notifies_changed_dict_item(self):
        notified = []
        items = [{"x": 1}, {"x": 2}]
        ns = _ns(items)
        for i, item in enumerate(items):
            child = DISCOSNamespace(ns._get_node(), i, {}, True)
            for k in item.keys():
                grandchild = DISCOSNamespace(item, k, {}, True)
                child._children[k] = grandchild
            child.bind(lambda v: notified.append(True))
            ns._children[i] = child
        ns <<= [{"x": 99}, {"x": 2}]
        self.assertTrue(len(notified) > 0)

    def test_update_list_plain_merge_dict_item_no_child(self):
        items = [{"x": 1, "y": 2}]
        wrapper = {"root": items}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        ns._update_list([{"x": 99, "y": 2}])
        self.assertEqual(items[0]["x"], 99)

    def test_make_dynamic_child_primitive_node(self):
        data = {"val": 42}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        object.__setattr__(ns, '_pattern_schemas', [
            (re.compile(r'^val$'), {"title": "Value"})
        ])
        child = ns._make_dynamic_child(data, "val")
        self.assertIsNotNone(child)
        self.assertEqual(child.get_value(), 42)

    def test_plain_merge_nested_dict_changed(self):
        target = {"sub": {"a": 1, "b": 2}}
        source = {"sub": {"a": 99, "b": 2}}
        changed = _plain_merge(target, source)
        self.assertTrue(changed)
        self.assertEqual(target["sub"]["a"], 99)

    def test_full_dict_includes_unwired_keys(self):
        data = {"wired": 1.0, "unwired": 42}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        wired_child = DISCOSNamespace(data, "wired", {"title": "Wired"}, True)
        ns._children["wired"] = wired_child
        result = orjson.loads(f"{ns:e}")
        self.assertIn("unwired", result)
        self.assertEqual(result["unwired"], 42)

    def test_merge_list_no_change(self):
        data = {"lst": [1, 2, 3]}
        wrapper = {"root": data}
        ns = DISCOSNamespace(wrapper, "root", {}, True)
        changed = ns._merge_dict(data, {"lst": [1, 2, 3]})
        self.assertFalse(changed)
        self.assertEqual(data["lst"], [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
