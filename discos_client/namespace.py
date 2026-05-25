from __future__ import annotations
import threading
from copy import deepcopy
from typing import Any, Callable, Iterator
import orjson
from .utils import delegated_operations, delegated_comparisons, META_KEYS


__all__ = ["DISCOSNamespace"]


def _plain_merge(target: dict, source: dict) -> bool:
    """Recursively merge *source* into *target* without any namespace
    involvement.  Used for dict sub-nodes that have no pre-built child
    namespace (e.g. dynamic pattern-property keys not yet in the tree).

    :return: True if at least one value changed.
    """
    changed = False
    for k, v in source.items():
        tv = target.get(k)
        if isinstance(v, dict) and isinstance(tv, dict):
            if _plain_merge(tv, v):
                changed = True
        elif tv != v:
            target[k] = v
            changed = True
    return changed


def _snapshot_tree(
    parent_container: dict | list,
    key: str | int,
    schema_meta: dict,
    orig_children: dict
) -> "DISCOSNamespace":
    """Recursively build a non-reactive snapshot namespace pointing into a
    *copy* of the data.  Used by :meth:`DISCOSNamespace.__copy__` and
    :meth:`DISCOSNamespace.__deepcopy__`.
    """
    ns = DISCOSNamespace(parent_container, key, schema_meta, reactive=False)
    node = parent_container[key]
    if isinstance(node, dict):
        for k, child in orig_children.items():
            if k in node:
                child_snap = _snapshot_tree(
                    node, k,
                    child._schema_meta,
                    child._children
                )
                ns._children[k] = child_snap
    elif isinstance(node, list):
        for i in range(len(node)):
            child = orig_children.get(i)
            if child is not None:
                child_snap = _snapshot_tree(
                    node, i,
                    child._schema_meta,
                    child._children
                )
                ns._children[i] = child_snap
    return ns


@delegated_operations('__value_operation__')
@delegated_comparisons('__value_comparison__')
class DISCOSNamespace:
    """Stable view node over a shared plain-dict data store.

    The tree of :class:`DISCOSNamespace` objects is built once by
    :class:`~discos_client.initializer.NSInitializer` and never structurally
    changes (except for array resizes and new dynamic keys).  All actual data
    lives in a plain Python dict/list hierarchy; each node keeps a reference
    to its *parent container* and its *key* inside that container, so that
    :meth:`_get_node` amounts to a single ``O(1)`` dict/list lookup.

    Consequences of this design:

    * Object identity is **stable**:
      ``client.antenna is client.antenna`` → True.
    * ``<<=`` is a plain ``dict`` deep-merge with no per-node object
      allocation, dropping the recursive :class:`DISCOSNamespace` traversal.
    * Serialisation (``format``, ``str``) calls ``json.dumps`` directly on
      the plain data dict — pure C, no Python ``unwrap`` recursion.
    * Per-node :class:`threading.RLock` is gone; the GIL protects single-
      bytecode reads/writes (see analysis in commit history).  Only the
      observer list uses an explicit :class:`threading.Lock`.
    """

    __typename__ = "DISCOSNamespace"

    def __init__(
        self,
        parent_dict: dict | list,
        key: str | int,
        schema_meta: dict | None = None,
        reactive: bool = True,
    ) -> None:
        """
        :param parent_dict: The dict or list that *contains* this node.
        :param key: The key / index of this node inside *parent_dict*.
        :param schema_meta: Static metadata extracted from the JSON Schema
                            (``title``, ``description``, ``unit``, ``enum``,
                            ``format``, ``type``).
        :param reactive: Whether to expose ``bind``, ``unbind``, ``wait`` and
                         ``copy``.
        """
        object.__setattr__(self, '_parent_dict', parent_dict)
        object.__setattr__(self, '_key', key)
        object.__setattr__(self, '_schema_meta', schema_meta or {})
        object.__setattr__(self, '_item_full_meta', {})
        object.__setattr__(self, '_pattern_schemas', [])
        object.__setattr__(self, '_children', {})
        object.__setattr__(self, '_reactive', reactive)
        if reactive:
            object.__setattr__(self, '_observers', [])
            object.__setattr__(self, '_observers_lock', threading.Lock())
            object.__setattr__(self, 'bind', self.__bind__)
            object.__setattr__(self, 'unbind', self.__unbind__)
            object.__setattr__(self, 'wait', self.__wait__)
            object.__setattr__(self, 'copy', self.__copy__)
        node = parent_dict[key]
        if not isinstance(node, (dict, list)):
            object.__setattr__(self, 'get_value', self.__get_value__)

    def _get_node(self) -> Any:
        """Return the current value of this node (single dict/list lookup)."""
        return self._parent_dict[self._key]

    def __get_value__(self) -> Any:
        """Return the primitive value held by this leaf node.

        :raises TypeError: If this node contains a dict or list.
        """
        node = self._parent_dict[self._key]
        if isinstance(node, (dict, list)):
            raise TypeError(
                f"{self.__typename__} does not hold a primitive value"
            )
        return node

    def __getattr__(self, name: str) -> Any:
        """Return a pre-built child namespace or a schema metadata value.

        Attribute access never traverses the data dict; child namespaces are
        looked up in ``_children`` by name, which is an ``O(1)`` dict lookup.

        :raises AttributeError: If the attribute is not found.
        """
        children = object.__getattribute__(self, '_children')
        if name in children:
            return children[name]
        meta = object.__getattribute__(self, '_schema_meta')
        if name in meta:
            return meta[name]
        node = object.__getattribute__(self, '_parent_dict')[
            object.__getattribute__(self, '_key')
        ]
        if not isinstance(node, (dict, list)) and node is not None:
            try:
                return getattr(node, name)
            except AttributeError:
                pass
        raise AttributeError(
            f"'{self.__typename__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            f"{self.__typename__} is read-only and "
            "does not allow attribute assignment"
        )

    def __delattr__(self, name: str) -> None:
        raise TypeError(
            f"{self.__typename__} is read-only and "
            "does not allow attribute deletion"
        )

    def __getitem__(self, item: int) -> Any:
        """Return the indexed child namespace for array nodes.

        :raises TypeError: If this node has no indexed children.
        """
        children = self._children
        if item in children:
            return children[item]
        raise TypeError(f"{self.__typename__} object is not subscriptable")

    def __len__(self) -> int:
        node = self._get_node()
        if isinstance(node, (list, tuple)):
            return len(node)
        raise TypeError(f"{self.__typename__} object has no length")

    def __iter__(self) -> Iterator:
        node = self._get_node()
        if isinstance(node, list):
            children = self._children
            return (children[i] for i in range(len(node)))
        raise TypeError(f"{self.__typename__} object is not iterable")

    def __bool__(self) -> bool:
        node = self._get_node()
        if isinstance(node, (bool, int, float, str)):
            return bool(node)
        raise TypeError(
            f"{self.__typename__} object cannot be converted to bool"
        )

    def __int__(self) -> int:
        node = self._get_node()
        if isinstance(node, (int, float)):
            return int(node)
        raise TypeError(
            f"{self.__typename__} object cannot be converted to int"
        )

    def __float__(self) -> float:
        node = self._get_node()
        if isinstance(node, (int, float)):
            return float(node)
        raise TypeError(
            f"{self.__typename__} object cannot be converted to float"
        )

    def __neg__(self) -> Any:
        node = self._get_node()
        if isinstance(node, (int, float)):
            return -node
        raise TypeError(f"{self.__typename__} object cannot be negated")

    def __abs__(self) -> Any:
        node = self._get_node()
        if isinstance(node, (int, float)):
            return abs(node)
        raise TypeError(f"{self.__typename__} object is not a numeric type.")

    def __round__(self, n: int = 0) -> Any:
        node = self._get_node()
        if isinstance(node, (int, float)):
            return round(node, n)
        raise TypeError(f"{self.__typename__} object cannot be rounded.")

    def __value_operation__(self, operation: Callable[[Any], Any]) -> Any:
        node = self._get_node()
        if not isinstance(node, (dict, list)) and node is not None:
            return operation(node)
        raise TypeError(
            f"{self.__typename__} supports operations "
            "only when holding a primitive value"
        )

    def __value_comparison__(
        self,
        op: Callable[[Any, Any], bool],
        other: Any
    ) -> bool | type(NotImplemented):
        if isinstance(other, DISCOSNamespace):
            try:
                return op(self._get_node(), other._get_node())
            except TypeError:
                return False
        node = self._get_node()
        if not isinstance(node, (dict, list)):
            return op(node, other)
        return NotImplemented

    def __ilshift__(self, other: Any) -> "DISCOSNamespace":
        """Update this node in-place with *other*.

        * **dict** → deep-merge into the data dict, notify changed nodes.
        * **list** → update array contents, rebuild children if length changed.
        * **DISCOSNamespace** → unwrap and apply its current data.
        * **primitive** → update the stored scalar value.

        :raises TypeError: If *other* has an unsupported type.
        """
        if self is other:
            return self
        if isinstance(other, DISCOSNamespace):
            other = other._get_node()
        node = self._get_node()
        if isinstance(other, dict) and isinstance(node, dict):
            if self._merge_dict(node, other):
                self.__notify__()
        elif isinstance(other, list):
            self._update_list(other)
        elif isinstance(other, (bool, int, float, str)) or other is None:
            if node != other:
                self._parent_dict[self._key] = other
                self.__notify__()
        else:
            raise TypeError(
                f"Unsupported operand type for <<=: "
                f"'{type(self).__name__}' and '{type(other).__name__}'"
            )
        return self

    def _merge_dict(self, target: dict, source: dict) -> bool:
        """Deep-merge *source* into *target*, notifying changed child nodes.

        Delegates each key to one of three helpers depending on the value
        type, keeping this method within pylint's branch limit.

        :return: True if at least one value changed.
        """
        changed = False
        children = self._children
        children_get = children.get
        target_get = target.get

        for k, v in source.items():
            tv = type(v)
            if tv is dict:
                if self._merge_dict_value(
                    target, children, k, v, target_get, children_get
                ):
                    changed = True
            elif tv is list:
                if self._merge_list_value(
                    target, k, v, target_get, children_get
                ):
                    changed = True
            else:
                if self._merge_scalar_value(
                    target, k, v, target_get, children_get
                ):
                    changed = True
        return changed

    def _merge_dict_value(
        self,
        target: dict,
        children: dict,
        k: str,
        v: dict,
        target_get,
        children_get,
    ) -> bool:
        """Handle a single dict-typed value during a merge."""
        target_v = target_get(k)
        child_ns = children_get(k)
        if isinstance(target_v, dict):
            if child_ns is not None:
                if child_ns._merge_dict(target_v, v):
                    child_ns.__notify__()
                    return True
            else:
                return _plain_merge(target_v, v)
        else:
            target[k] = dict(v)
            child_ns = self._make_dynamic_child(target, k)
            if child_ns is not None:
                children[k] = child_ns
            return True
        return False

    def _merge_list_value(
        self,
        target: dict,
        k: str,
        v: list,
        target_get,
        children_get,
    ) -> bool:
        """Handle a single list-typed value during a merge."""
        child_ns = children_get(k)
        if child_ns is not None:
            return child_ns._update_list(v)
        target_v = target_get(k)
        if target_v != v:
            target[k] = list(v)
            return True
        return False

    def _merge_scalar_value(
        self,
        target: dict,
        k: str,
        v,
        target_get,
        children_get,
    ) -> bool:
        """Handle a single scalar (non-dict, non-list) value during a merge."""
        target_v = target_get(k)
        if target_v is not v and target_v != v:
            target[k] = v
            child_ns = children_get(k)
            if child_ns is not None:
                child_ns.__notify__()
            return True
        return False

    def _update_list(self, new_list: list) -> bool:
        """Update this array node with *new_list*.

        If the length differs the list is replaced in-place and indexed
        children are rebuilt.  Otherwise each element is updated individually.

        :return: True if at least one value changed.
        """
        target = self._get_node()
        children = self._children

        if not isinstance(target, list) or len(target) != len(new_list):
            if isinstance(target, list):
                del target[:]
                target.extend(new_list)
            else:
                self._parent_dict[self._key] = list(new_list)
                target = self._get_node()
            self._rebuild_list_children(target)
            self.__notify__()
            return True

        changed = False
        for i, new_item in enumerate(new_list):
            old_item = target[i]
            child_ns = children.get(i)
            if isinstance(new_item, dict) and isinstance(old_item, dict):
                if child_ns is not None:
                    if child_ns._merge_dict(old_item, new_item):
                        child_ns.__notify__()
                        changed = True
                else:
                    if _plain_merge(old_item, new_item):
                        changed = True
            elif old_item != new_item:
                target[i] = new_item
                changed = True
                if child_ns is not None:
                    child_ns.__notify__()

        if changed:
            self.__notify__()
        return changed

    def _rebuild_list_children(self, target_list: list) -> None:
        """Rebuild indexed children after a list-length change.

        Uses :attr:`_item_full_meta` to build each child via
        :meth:`_build_ns_from_meta`, which recurses with full schema metadata.
        """
        children = self._children
        children.clear()
        item_full_meta = object.__getattribute__(self, '_item_full_meta')
        for i in range(len(target_list)):
            child_ns = self._build_ns_from_meta(target_list, i, item_full_meta)
            children[i] = child_ns

    def _make_dynamic_child(
        self,
        parent_data: dict,
        key: str,
    ) -> "DISCOSNamespace | None":
        """Create a namespace node for a previously unseen dynamic key.

        Iterates over :attr:`_pattern_schemas` to find a matching schema and
        builds the child namespace accordingly.  Returns ``None`` if no pattern
        matches (the data was still written; only the namespace wrapper is
        absent).
        """
        for rx, full_meta in self._pattern_schemas:
            if rx.fullmatch(str(key)):
                top_meta = {
                    k: v
                    for k, v in full_meta.items()
                    if k in META_KEYS
                }
                child_ns = DISCOSNamespace(
                    parent_data, key, top_meta, self._reactive
                )
                node = parent_data[key]
                if isinstance(node, dict):
                    for k, v in node.items():
                        child_meta_tree = full_meta.get(k, {})
                        grandchild = self._build_ns_from_meta(
                            node,
                            k,
                            child_meta_tree
                        )
                        child_ns._children[k] = grandchild
                elif not isinstance(node, list):
                    object.__setattr__(child_ns, 'get_value',
                                       child_ns.__get_value__)
                return child_ns
        return None

    def _build_ns_from_meta(self, parent_data, key, meta_tree):
        top_meta = {k: v for k, v in meta_tree.items() if k in META_KEYS}
        ns = DISCOSNamespace(parent_data, key, top_meta, self._reactive)
        node = parent_data[key]
        if isinstance(node, dict):
            for k, v in node.items():
                child_meta = meta_tree.get(k, {})
                grandchild = self._build_ns_from_meta(node, k, child_meta)
                ns._children[k] = grandchild
        elif isinstance(node, list):
            item_meta = meta_tree.get("items", [{}])
            if isinstance(item_meta, list):
                item_meta = item_meta[0]
            object.__setattr__(ns, '_item_full_meta', item_meta)
            for i, _ in enumerate(node):
                child = self._build_ns_from_meta(node, i, item_meta)
                ns._children[i] = child
        else:
            object.__setattr__(ns, 'get_value', ns.__get_value__)
        return ns

    def __notify__(self) -> None:
        """Fire registered callbacks if any.

        The first check (``if not self._observers``) is a single
        ``LOAD_ATTR`` + truth-check — atomic under CPython's GIL — so no lock
        is acquired when there are no observers (the common case on most
        nodes). The lock is taken only when there are callbacks to snapshot and
        invoke.
        """
        if not self._reactive:
            return
        observers = self._observers  # atomic read under GIL
        if not observers:
            return
        with self._observers_lock:
            observers = list(self._observers)
        for cb, pred, unwrap in observers:
            value = self._get_node() if unwrap else self
            if pred is None or pred(value):
                cb(value)

    def __bind__(
        self,
        callback: Callable[[Any], None],
        predicate: Callable[[Any], bool] | None = None,
        unwrap: bool = False,
    ) -> None:
        """Register *callback* to be called when this node changes.

        :param callback: Called with the updated node (or its raw value when
                         *unwrap* is True).
        :param predicate: Optional filter; the callback fires only when the
                          predicate returns True.
        :param unwrap: If True, the predicate and callback receive the raw
                       primitive value instead of the namespace node.
        """
        with self._observers_lock:
            self._observers.append((callback, predicate, unwrap))

    def __unbind__(
        self,
        callback: Callable[[Any], None] | None = None,
        predicate: Callable[[Any], bool] | None = None,
    ) -> None:
        """Remove a previously registered callback.

        :param callback: The callback to remove.  If ``None``, all callbacks
                         are removed.
        :param predicate: If given, only the entry with this exact predicate
                          is removed; other entries for the same callback are
                          kept.
        """
        with self._observers_lock:
            if callback is None:
                self._observers.clear()
                return
            self._observers[:] = [
                (cb, pred, uw)
                for cb, pred, uw in self._observers
                if not (
                    cb == callback
                    and (predicate is None or pred == predicate)
                )
            ]

    def __wait__(
        self,
        predicate: Callable[[Any], bool] | None = None,
        timeout: float | None = None,
        unwrap: bool = False,
    ) -> Any:
        """Block until this node changes (and optionally satisfies
        *predicate*).

        :param predicate: If given, keeps waiting until the predicate returns
                          True.
        :param timeout: Maximum wait time in seconds.
        :param unwrap: If True, returns the raw primitive value instead of the
                       namespace node.
        :return: This node (or its raw value if *unwrap*) after the change.
        """
        event = threading.Event()

        def _cb(_: Any) -> None:
            event.set()

        self.bind(_cb, predicate, unwrap=unwrap)
        try:
            event.wait(timeout)
        finally:
            self.unbind(_cb, predicate)
        node = self._get_node()
        if unwrap and not isinstance(node, (dict, list)):
            return node
        return self

    def __copy__(self) -> "DISCOSNamespace":
        """Return an independent, non-reactive snapshot of the current state.

        The data dict is deep-copied so subsequent updates to the live tree do
        not affect the snapshot.  The namespace structure mirrors the original
        but holds no observers.
        """
        data_copy = deepcopy(self._get_node())
        wrapper = {self._key: data_copy}
        return _snapshot_tree(
            wrapper, self._key,
            self._schema_meta,
            self._children
        )

    def __repr__(self) -> str:
        node = self._get_node()
        if not isinstance(node, (dict, list)):
            return repr(node)
        return f"<{self.__typename__}({node})>"

    def __str__(self) -> str:
        return format(self, "")

    def __format__(self, spec: str) -> str:
        """Format this namespace as a JSON string using :mod:`orjson`.

        :param spec: Format specifier.

            | ``''`` - default JSON (data values only, compact)
            | ``'i'`` - indented JSON (fixed at 2 spaces)
            | ``'e'`` - full JSON including schema metadata
            | ``'m'`` - metadata-only JSON (no data values)
            | ``'w'`` - wrap the output in ``{node_key: ...}``

            Specs can be combined, e.g. ``'wi'``, ``'ei'``, ``'mi'``.
            ``'t'`` (tight) is accepted as an alias for ``''`` since
            :mod:`orjson` always produces compact output by default.

        :return: A JSON-formatted string.
        :raises ValueError: For unknown or conflicting format specifiers.
        """
        has_e = "e" in spec
        has_m = "m" in spec
        has_w = "w" in spec
        has_i = "i" in spec

        if has_e and has_m:
            raise ValueError(
                "Format specifier cannot contain both 'e' and 'm'."
            )

        node = self._get_node()
        if (not isinstance(node, (dict, list)) and
                not (has_e or has_m or has_w)):
            return format(node, spec)

        fmt_spec = spec
        for ch in ("e", "m", "w", "i"):
            fmt_spec = fmt_spec.replace(ch, "")

        if fmt_spec not in ("", "t"):
            raise ValueError(
                f"Unknown format code '{spec}' for {self.__typename__}"
            )

        if has_e:
            data = self._full_dict()
        elif has_m:
            data = self._meta_dict()
        else:
            data = node

        if has_w:
            if self._key is None:
                raise ValueError("Cannot wrap node without a key!")
            data = {self._key: data}

        option = orjson.OPT_SORT_KEYS
        if has_i:
            option |= orjson.OPT_INDENT_2

        return orjson.dumps(data, option=option).decode()

    def _full_dict(self) -> Any:
        """Return a dict merging data values and schema metadata.

        Used by the ``'e'`` format specifier.  Not in the hot path.
        """
        node = self._get_node()
        if isinstance(node, dict):
            result = dict(self._schema_meta)
            for k, child in self._children.items():
                result[k] = child._full_dict()
            for k, v in node.items():
                if k not in result:
                    result[k] = v
            return result
        if isinstance(node, list):
            result = dict(self._schema_meta)
            result["items"] = [
                self._children[i]._full_dict()
                if i in self._children else item
                for i, item in enumerate(node)
            ]
            return result
        result = dict(self._schema_meta)
        result["value"] = node
        return result

    def _meta_dict(self) -> dict:
        """Return the schema-metadata tree without any data values.

        Used by the ``'m'`` format specifier.  Not in the hot path.
        """
        result = dict(self._schema_meta)
        node = self._get_node()
        if isinstance(node, list):
            item_full_meta = object.__getattribute__(self, "_item_full_meta")
            if item_full_meta:
                result["items"] = [item_full_meta]
        else:
            for k, child in self._children.items():
                child_meta = child._meta_dict()
                if child_meta:
                    result[str(k)] = child_meta
        return result

    @classmethod
    def __full_dict__(cls, obj: "DISCOSNamespace") -> Any:
        """JSON ``default`` hook: returns the enriched (data + meta) dict."""
        return obj._full_dict()

    @classmethod
    def __message_dict__(cls, obj: "DISCOSNamespace") -> Any:
        """JSON ``default`` hook: returns the plain data dict."""
        return obj._get_node()

    @classmethod
    def __metadata_dict__(cls, obj: "DISCOSNamespace") -> dict:
        """JSON ``default`` hook: returns the metadata-only dict."""
        return obj._meta_dict()

    def __deepcopy__(self, memo: dict) -> "DISCOSNamespace":
        """Produce a fully independent deep copy (data + namespace structure).

        Schema metadata (static) is shared rather than copied.
        """
        new_parent = deepcopy(self._parent_dict, memo)
        return _snapshot_tree(
            new_parent, self._key,
            self._schema_meta,
            self._children
        )

    def __dir__(self) -> list[str]:
        attrs = set(super().__dir__())
        attrs.update(str(k) for k in self._children)
        attrs.update(self._schema_meta)
        node = self._parent_dict[self._key]
        if not isinstance(node, (dict, list)) and node is not None:
            attrs.update(dir(node))
        return sorted(attrs)
