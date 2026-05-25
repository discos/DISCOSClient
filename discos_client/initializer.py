from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from importlib.resources import files
from collections.abc import Iterable
import orjson
from .utils import META_KEYS
from .namespace import DISCOSNamespace


__all__ = ["NSInitializer"]


class NSInitializer:
    """
    Load, normalize and initialize JSON Schemas for DISCOS topics.

    This class loads all schema files under ``schemas/common`` and,
    optionally, ``schemas/<telescope>``, resolves and expands references,
    merges ``allOf`` blocks, precompiles ``patternProperties`` and
    builds a mapping between logical topic names and absolute schema IDs.

    It finally provides :meth:`initialize`, which constructs the initial
    :class:`~discos_client.namespace.DISCOSNamespace` tree for a topic.
    The tree is a **stable view** over a shared plain-dict data store:
    each namespace node holds a reference to its parent container and key
    rather than owning its value directly.
    """

    def __init__(self, telescope: str | None = None):
        """
        Initialize the initializer and load all schemas from disk.

        This sets up the schema dictionaries, expands references,
        merges ``allOf`` and precompiles ``patternProperties`` for
        both common and telescope-specific schemas.

        :param telescope: Optional telescope identifier; if provided, schemas
                          in the corresponding subdirectory are loaded in
                          addition to the common ones.
        """
        base_dir = files("discos_client") / "schemas"
        self._pp_cache: \
            dict[int, list[tuple[str, "re.Pattern | None", dict]]] = {}
        self.schemas, definitions, self.node_to_id = \
            self._load_schemas(base_dir, telescope)

        for def_id, definition in definitions.items():
            definition = self._absolutize_refs(definition, base_dir, def_id)
            definition = self._expand_refs(definition, definitions)
            definition = self._merge_all_of(definition)
            self._precompile_patternprops(definition)
            definitions[def_id] = definition

        for schema_id, schema in self.schemas.items():
            schema = self._absolutize_refs(schema, base_dir, schema_id)
            schema = self._expand_refs(schema, definitions)
            schema = self._merge_all_of(schema)
            schema.pop("$defs", None)
            self._precompile_patternprops(schema)
            self.schemas[schema_id] = schema

        self.available_topics = list(self.node_to_id.keys())
        self.available_topics.remove("command_answer")

    def initialize(
        self,
        topic: str,
        reactive: bool = True,
    ) -> DISCOSNamespace:
        """
        Build the initial :class:`~discos_client.namespace.DISCOSNamespace`
        tree for the given topic.

        The tree is a **stable view** over a freshly allocated plain-dict
        data store.  The dict is populated with ``None`` for all primitive
        leaves and empty dicts/lists for object/array nodes, covering every
        field declared as ``required`` or ``initialize`` in the schema.

        The namespace tree mirrors this dict structure: each node holds a
        reference to its *parent container* and its *key* rather than
        embedding the value.  Serialisation and updates both operate on the
        plain dict, keeping DISCOSNamespace out of the hot path.

        :param topic: Logical topic name (schema ``node`` value).
        :param reactive: Whether to attach ``bind`` / ``unbind`` / ``wait``
                         to the namespace nodes.
        :return: A fully initialised namespace tree ready to receive updates.
        :raises ValueError: If the topic does not correspond to a loaded
                            schema.
        """
        if topic not in self.node_to_id:  # pragma: no cover
            raise ValueError(f"Schema '{topic}' was not loaded.")
        schema = self.schemas[self.node_to_id[topic]]
        data = self._build_data_dict(schema)
        wrapper: dict[str, Any] = {topic: data}
        return self._build_ns_tree(wrapper, topic, schema, reactive)

    def get_topics(self) -> list[str]:
        """
        Return the list of available logical topic names.

        :return: All topic names loaded from schema files.
        """
        return self.available_topics

    def _build_data_dict(self, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Build an initial **plain** data dict from *schema*.

        Only structural types are represented — no schema metadata is
        embedded.  Required and ``initialize`` fields are included;
        optional fields absent from ``initialize`` are omitted.

        :param schema: Fully resolved and merged JSON Schema object.
        :return: Plain dict with ``None`` for primitives, ``{}`` for objects,
                 ``[]`` for arrays.
        """
        result: dict[str, Any] = {}
        required, initialize = self._collect_init_keys(schema)
        for key in required | initialize:
            prop_schema = self._find_property_schema(schema, key)
            if prop_schema is None:  # pragma: no cover
                continue
            result[key] = self._initial_value_for(prop_schema)
        return result

    def _initial_value_for(self, schema: dict[str, Any]) -> Any:
        """
        Return the appropriate initial value for a single property.

        :param schema: Property schema.
        :return: ``{}`` for objects, ``[]`` for arrays, ``None`` for
                 primitives.
        """
        t = schema.get("type")
        if t == "object":
            return self._build_data_dict(schema)
        if t == "array":
            return []
        return None

    def _build_ns_tree(
        self,
        parent_container: dict | list,
        key: str | int,
        schema: dict[str, Any],
        reactive: bool,
    ) -> DISCOSNamespace:
        """
        Recursively build a :class:`~discos_client.namespace.DISCOSNamespace`
        tree rooted at ``parent_container[key]``.

        The namespace node receives:

        * Schema metadata (``title``, ``description``, ``unit``, ``enum``,
          ``format``, ``type``) stored in ``_schema_meta``.
        * Pre-compiled ``patternProperties`` patterns stored in
          ``_pattern_schemas`` so that dynamically keyed children (e.g.
          individual backend or derotator instances) can be created on first
          arrival without a reference back to this initializer.
        * Pre-built child namespaces for every key present in the initial
          data dict (objects) or every index present in the initial list
          (arrays).

        :param parent_container: The dict or list containing the node to wrap.
        :param key: Key / index of the node inside *parent_container*.
        :param schema: JSON Schema for this node.
        :param reactive: Whether to attach reactive helpers to nodes.
        :return: Root of the constructed namespace sub-tree.
        """
        schema_meta = {k: schema[k] for k in META_KEYS if k in schema}
        ns = DISCOSNamespace(parent_container, key, schema_meta, reactive)
        node = parent_container[key]
        if isinstance(node, dict):
            self._attach_pattern_schemas(ns, schema)
            properties = schema.get("properties", {})
            required, initialize = self._collect_init_keys(schema)
            keys_to_build = (required | initialize) & set(node.keys())
            for k in keys_to_build:
                prop_schema = (
                    properties.get(k)
                    or self._find_property_schema(schema, k)
                    or {}
                )
                child_ns = self._build_ns_tree(node, k, prop_schema, reactive)
                ns._children[k] = child_ns
        elif isinstance(node, list):
            item_schema = schema.get("items") or {}
            item_full_meta = self._build_meta_from_schema(item_schema)
            object.__setattr__(ns, '_item_full_meta', item_full_meta)
            for i, _ in enumerate(node):
                child_ns = self._build_ns_tree(node, i, item_schema, reactive)
                ns._children[i] = child_ns
        return ns

    def _attach_pattern_schemas(
        self,
        ns: DISCOSNamespace,
        schema: dict[str, Any],
    ) -> None:
        """
        Populate ``_pattern_schemas`` on *ns* from the schema's
        ``patternProperties``, using the precompiled cache built during
        :meth:`__init__`.

        ``patternProperties`` is searched at two levels:

        * The top-level schema (e.g. active surface sector nodes).
        * Each branch of an ``anyOf`` block.  Schemas like ``backends``,
          ``receivers`` and ``derotators`` use ``anyOf`` with one fixed branch
          and one ``patternProperties`` branch for dynamically named instances
          (``SARDARA``, ``CCB``, etc.).  Without this second pass those topics
          would never get dynamic child namespaces created on first message
          arrival.

        This allows
        :meth:`~discos_client.namespace.DISCOSNamespace._merge_dict`
        to create namespace children for dynamic keys without holding a
        reference back to this initializer.

        :param ns: The namespace node to enrich.
        :param schema: The schema for that node, potentially containing
                       ``patternProperties`` at the top level or inside
                       ``anyOf`` branches.
        """
        pp_dicts = []
        top_pp = schema.get("patternProperties")
        if top_pp:
            pp_dicts.append(top_pp)
        for alt in schema.get("anyOf", []):
            if isinstance(alt, dict):
                alt_pp = alt.get("patternProperties")
                if alt_pp:
                    pp_dicts.append(alt_pp)

        if not pp_dicts:
            return

        pattern_schemas = []
        for pp in pp_dicts:
            pp_list = self._pp_cache.get(id(pp), [])
            for _, rx, pschema in pp_list:
                if rx is not None:
                    full_meta = self._build_meta_from_schema(pschema)
                    pattern_schemas.append((rx, full_meta))

        if pattern_schemas:
            object.__setattr__(ns, '_pattern_schemas', pattern_schemas)

    def _collect_init_keys(
        self,
        schema: dict[str, Any]
    ) -> tuple[set[str], set[str]]:
        """
        Recursively collect all ``required`` and ``initialize`` fields declared
        in a schema, including those defined inside ``anyOf`` branches.

        :param schema: A JSON Schema object, potentially containing ``anyOf``
                       branches and local ``required`` / ``initialize``
                       sections.
        :return: A tuple where each element is a set of field names
                 aggregated from the entire schema hierarchy.
        """
        required: set[str] = set(schema.get("required", []))
        initialize: set[str] = set(schema.get("initialize", []))

        any_of = schema.get("anyOf")
        if isinstance(any_of, list):
            for alt in any_of:
                if isinstance(alt, dict):
                    r_alt, i_alt = self._collect_init_keys(alt)
                    required |= r_alt
                    initialize |= i_alt

        return required, initialize

    def _find_property_schema(
        self,
        schema: dict[str, Any],
        key: str
    ) -> dict[str, Any] | None:
        """
        Locate the schema of a named property within a schema.

        The property is first searched in the top-level ``properties``
        dictionary, then inside any ``anyOf`` alternatives.

        :param schema: Schema object in which to search.
        :param key: Name of the property to look for.
        :return: The matching property schema, or ``None`` if not found.
        """
        props = schema.get("properties", {})
        if key in props:
            return props[key]
        any_of = schema.get("anyOf")
        if isinstance(any_of, list):
            for alt in any_of:
                if isinstance(alt, dict):
                    found = self._find_property_schema(alt, key)
                    if found is not None:
                        return found
        return None  # pragma: no cover

    def _precompile_patternprops(self, obj: dict | list) -> None:
        """
        Recursively scan a schema and precompile its ``patternProperties``.

        Compiled entries are cached to avoid repeated regex compilation.

        :param obj: Schema object to inspect.
        """
        for d in self._walk_dicts(obj):
            pp = d.get("patternProperties")
            if not isinstance(pp, dict) or not pp:
                continue
            key = id(pp)
            if key not in self._pp_cache:
                self._pp_cache[key] = self._build_pp_list(pp)

    def _walk_dicts(self, root: dict | list) -> Iterable[dict]:
        """
        Walk a nested schema structure and yield all dictionaries it contains.

        The traversal is depth-first and follows both dictionary values
        and list elements.

        :param root: Root schema object (dictionary or list) to traverse.
        :return: An iterator yielding all nested dictionaries.
        """
        stack: list[dict | list] = [root]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                yield cur
                for v in cur.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                for v in cur:
                    if isinstance(v, (dict, list)):
                        stack.append(v)

    def _build_pp_list(
        self,
        pp: dict
    ) -> list[tuple[str, re.Pattern | None, dict]]:
        """
        Convert a ``patternProperties`` dictionary into a list of compiled
        entries.

        Each entry contains:
        * the raw pattern string
        * the compiled regex (or ``None`` if compilation fails)
        * the associated property schema

        :param pp: Dictionary of raw patternProperties.
        :return: Precompiled patternProperties entries.
        """
        compiled: list[tuple[str, re.Pattern | None, dict]] = []
        for pat, pschema in pp.items():
            try:
                rx = re.compile(pat)
            except re.error:  # pragma: no cover
                rx = None
            compiled.append((pat, rx, pschema))
        return compiled

    def _load_schemas(
        self,
        base_dir: Path,
        telescope: str | None
    ) -> tuple[dict[str, dict], dict[str, dict], dict[str, str]]:
        """
        Load schema and definition files from disk.

        This loads:
        * Reusable definitions from ``schemas/definitions``.
        * Common schemas from ``schemas/common``.
        * Telescope-specific schemas if requested.

        It also builds the ``node_to_id`` mapping from topic names to
        canonical schema identifiers.

        :param base_dir: Base directory containing the schema tree.
        :param telescope: Optional telescope name.
        :return: A tuple ``(schemas, definitions, node_to_id)``.
        :raises FileNotFoundError: If the definitions directory is missing.
        :raises ValueError: If a schema is missing its ``node`` field.
        """
        schemas_dirs = [base_dir / "common"]
        if telescope:
            schemas_dirs.append(base_dir / telescope.lower())
        schemas: dict[str, dict] = {}
        definitions: dict[str, dict] = {}
        node_to_id: dict[str, str] = {}
        definitions_dir = base_dir / "definitions"
        if not definitions_dir.exists():  # pragma: no cover
            raise FileNotFoundError(f"{definitions_dir} not found")
        for f in definitions_dir.iterdir():
            if f.is_file() and f.name.endswith(".json"):
                rel_path = f.resolve().relative_to(base_dir).as_posix()
                schema = orjson.loads(f.read_text(encoding="utf-8"))
                self._absolutize_refs(schema, base_dir, rel_path)
                schema_id = schema.get("$id", rel_path)
                definitions[schema_id] = schema
        for d in schemas_dirs:
            for f in d.iterdir():
                if f.is_file() and f.name.endswith(".json"):
                    rel_path = \
                        f.resolve().relative_to(base_dir).as_posix()
                    schema = orjson.loads(f.read_text(encoding="utf-8"))
                    self._absolutize_refs(schema, base_dir, rel_path)
                    schema_id = schema.get("$id", rel_path)
                    node_name = schema.get("node")
                    if not node_name:  # pragma: no cover
                        raise ValueError(f"Missing 'node' field in {rel_path}")
                    node_to_id[node_name] = schema_id
                    schemas[schema_id] = schema
                    for k, v in schema.get("$defs", {}).items():
                        definitions[f"{schema_id}#/$defs/{k}"] = v
        return schemas, definitions, node_to_id

    def _absolutize_refs(
        self,
        schema: dict[str, Any],
        base_dir: Path,
        current_file: str
    ) -> dict[str, Any]:
        """
        Rewrite all ``$ref`` values in a schema to canonical absolute paths.

        :param schema: Schema whose references will be rewritten in-place.
        :param base_dir: Base directory containing the schema tree.
        :param current_file: Path of the schema file currently being processed,
                             relative to ``base_dir``.
        :return: The same schema dictionary, with normalized ``$ref`` values.
        """
        def recurse(obj: Any):
            if isinstance(obj, dict):
                if "$ref" in obj:
                    obj["$ref"] = self._normalize_ref(
                        obj["$ref"],
                        base_dir,
                        Path(current_file)
                    )
                for v in obj.values():
                    recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)
        recurse(schema)
        return schema

    def _normalize_ref(
        self,
        ref: str,
        base_dir: Path,
        current_file: Path
    ) -> str:
        """
        Normalize a single ``$ref`` value into an absolute, canonical form.

        :param ref: Raw reference string as found in the schema.
        :param base_dir: Base directory containing all schemas.
        :param current_file: Path of the file that owns the reference.
        :return: Normalized reference string suitable for dictionary lookups.
        """
        if ref.startswith("#"):
            return f"{current_file.as_posix()}{ref}"
        current_file = base_dir / current_file
        current_dir = current_file.parent
        ref_path, _, fragment = ref.partition("#")
        ref_path = Path(ref_path)
        if ".." in ref_path.as_posix():
            current_ref = current_dir / ref_path
            base_dir = base_dir.resolve()
            current_ref = current_ref.resolve()
            result = current_ref.relative_to(base_dir)
        else:
            result = ref_path
        result = result.as_posix()
        return f"{result}#{fragment}" if fragment else result

    def _expand_refs(
        self,
        schema: dict[str, Any],
        definitions: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Recursively resolve all ``$ref`` occurrences inside a schema.

        :param schema: Schema containing references.
        :param definitions: Mapping of absolute definition identifiers to their
                            content.
        :return: Schema with all references expanded.
        :raises ValueError: If a ``$ref`` cannot be resolved.
        """
        def recurse(obj: Any):
            if isinstance(obj, dict):
                if "$ref" in obj:
                    ref = obj["$ref"]
                    resolved = definitions.get(ref)
                    if not resolved:  # pragma: no cover
                        raise ValueError(f"Unresolved $ref: {ref}")
                    merged = {
                        **resolved,
                        **{k: v for k, v in obj.items() if k != "$ref"}
                    }
                    return recurse(merged)
                return {k: recurse(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [recurse(item) for item in obj]
            return obj
        return recurse(schema)

    def _merge_all_of(self, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively merge all ``allOf`` blocks in the schema.

        :param schema: Schema object containing ``allOf`` blocks.
        :return: Schema with all ``allOf`` sections flattened.
        """
        def recurse(obj: Any):
            if isinstance(obj, dict):
                if "allOf" in obj:
                    merged = self._merge_subschemas(obj["allOf"])
                    return recurse(merged)
                return {k: recurse(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [recurse(item) for item in obj]
            return obj
        return recurse(schema)

    def _merge_subschemas(
        self,
        subschemas: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Merge multiple subschemas into a single schema object.

        :param subschemas: List of schema fragments to merge.
        :return: A single schema representing the merged subschemas.
        """
        merged: dict[str, Any] = {}
        required_fields: set[str] = set()
        initialize_fields: set[str] = set()
        for subschema in subschemas:
            subschema = self._merge_all_of(subschema)
            merged.setdefault("properties", {}).update(
                subschema.get("properties", {})
            )
            merged.setdefault("patternProperties", {}).update(
                subschema.get("patternProperties", {})
            )
            required_fields.update(subschema.get("required", []))
            init_list = subschema.get("initialize")
            if isinstance(init_list, list):
                for key in init_list:
                    if isinstance(key, str):
                        initialize_fields.add(key)
            for k, v in subschema.items():
                if k in ("properties", "patternProperties",
                         "required", "allOf", "initialize"):
                    continue
                merged[k] = v
        if required_fields:
            merged["required"] = list(sorted(required_fields))
        if initialize_fields:
            merged["initialize"] = list(sorted(initialize_fields))
        return merged

    def _build_meta_from_schema(self, schema: dict) -> dict:
        result = {k: schema[k] for k in META_KEYS if k in schema}
        for key, prop_schema in schema.get("properties", {}).items():
            child_meta = self._build_meta_from_schema(prop_schema)
            if child_meta:
                result[key] = child_meta
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            item_meta = self._build_meta_from_schema(items_schema)
            if item_meta:
                result["items"] = [item_meta]
        return result
