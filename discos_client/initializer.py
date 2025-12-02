from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Any
from importlib.resources import files
from collections.abc import Iterable
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
    `DISCOSNamespace` tree for a topic, enriched with schema metadata
    and with all required/initialized fields present.
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
            dict[int, list[tuple[str, "re.Pattern", str, dict]]] = {}
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

    def initialize(
        self,
        topic: str
    ) -> DISCOSNamespace:
        """
        Build the initial :class:`DISCOSNamespace` for the given topic.

        The namespace contains:
        * All required fields from the schema.
        * All fields listed in the schema's ``initialize`` array.
        * Metadata fields copied from the schema.
        * Proper structure for objects, arrays and primitives.

        :param topic: Logical topic name (schema ``node`` value).
        :return: A fully initialized namespace tree ready to receive updates.
        :raises ValueError: If the topic does not correspond to a loaded
                            schema.
        """
        if topic not in self.node_to_id:  # pragma: no cover
            raise ValueError(f"Schema '{topic}' was not loaded.")
        topic = self.node_to_id[topic]
        schema = self.schemas[topic]
        payload = self._initialize_from_schema(schema)
        return DISCOSNamespace(schema=schema, **payload)

    def get_topics(self) -> list[str]:
        """
        Return the list of available logical topic names.

        :return: All topic names loaded from schema files.
        """
        return list(self.node_to_id.keys())

    def _literal_prefix(self, pat: str) -> str:
        """
        Extract the literal prefix of a regex pattern.

        The prefix consists of non-metacharacter characters up to the first
        special symbol and is used to optimize ``patternProperties`` matching.

        :param pat: Regular expression pattern.
        :return: Literal prefix extracted from the pattern.
        """
        i = 0
        if pat.startswith('^'):
            i = 1
        out = []
        meta = set('.^$*+?[]{}()|\\')
        while i < len(pat):
            c = pat[i]
            if c in meta:
                break
            out.append(c)  # pragma: no cover
            i += 1  # pragma: no cover
        return ''.join(out)

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
    ) -> list[tuple[str, re.Pattern | None, str, dict]]:
        """
        Converts a ``patternProperties`` dictionary into a list of compiled
        entries.

        Each entry contains:
        * the raw pattern
        * the compiled regex (or ``None`` if invalid)
        * the literal prefix
        * the associated property schema

        :param pp: Dictionary of raw patternProperties.

        :return: Precompiled patternProperties entries.
        """
        compiled: list[tuple[str, re.Pattern | None, str, dict]] = []
        for pat, pschema in pp.items():
            try:
                rx = re.compile(pat)
            except re.error:  # pragma: no cover
                rx = None
            pref = self._literal_prefix(pat)
            compiled.append((pat, rx, pref, pschema))
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
                schema = json.loads(f.read_text(encoding="utf-8"))
                self._absolutize_refs(schema, base_dir, rel_path)
                schema_id = schema.get("$id", rel_path)
                definitions[schema_id] = schema
        for d in schemas_dirs:
            for f in d.iterdir():
                if f.is_file() and f.name.endswith(".json"):
                    rel_path = \
                        f.resolve().relative_to(base_dir).as_posix()
                    schema = json.loads(f.read_text(encoding="utf-8"))
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

        Relative references are normalized with respect to the current
        file and base directory so they can be resolved consistently.

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

        This handles:
        * Pure fragment references (starting with ``#``).
        * Relative paths (including ``..`` segments) resolved against
          the current file and base directory.
        * Optional fragments appended to the resolved path.

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

        Referenced definitions are merged with inline overrides.

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

        ``properties`` and ``patternProperties`` are combined,
        ``required`` fields are unioned, and ``initialize`` arrays are merged.

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

        This helper is used to flatten ``allOf`` blocks. It:

        * Merges ``properties`` and ``patternProperties``.
        * Unions all ``required`` fields.
        * Unions all ``initialize`` fields.
        * Copies any other keys, letting later subschemas override
          earlier ones.

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

    def _replace_patterns_with_properties(
        self,
        schema: dict[str, Any],
        message: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Optionally strip ``patternProperties`` from a schema.

        If no message data is available, any ``patternProperties`` section
        is removed from the returned schema copy. Otherwise the schema
        is left unchanged.

        :param schema: Schema object that may contain ``patternProperties``.
        :param message: Message payload used to decide whether patterns should
                        be retained or removed.
        :return: The original schema or a shallow copy without
                 ``patternProperties``.
        """
        pp = schema.get("patternProperties")
        if not pp or not message:
            if "patternProperties" in schema:
                out = dict(schema)
                out.pop("patternProperties", None)
                return out
        return schema

    def _enrich_properties(
        self,
        schema: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enrich all relevant properties for an object schema.

        Only properties that are required or present in ``values`` are
        processed. Each selected property is converted into its enriched
        representation, including metadata and nested structures.

        :param schema: Object schema definition.
        :param values: Current values for the object, used to decide which
                       properties to include and how to initialize them.
        :return: A dictionary mapping property names to enriched values.
        """
        schema = self._replace_patterns_with_properties(schema, values)
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        initialize = set(schema.get("initialize", []))
        result: dict[str, Any] = {}
        for key, prop_schema in properties.items():
            if key in required.union(initialize) or key in values:
                prop_schema = self._replace_patterns_with_properties(
                    prop_schema,
                    values.get(key, {})
                )
                result[key] = self._enrich_named_property(
                    key, prop_schema, values
                )
        return result

    def _meta(self, d: dict[str, Any]) -> dict[str, Any]:
        """
        Extract metadata keys from a schema dictionary.

        Only keys listed in :data:`META_KEYS` are preserved.

        :param d: Source dictionary, typically a schema fragment.
        :return: Dictionary containing only the metadata entries.
        """
        return {
            k: d[k]
            for k in META_KEYS
            if k in d
        }

    def _without(self, d: dict[str, Any], *keys: str) -> dict[str, Any]:
        """
        Return a shallow copy of a dictionary without the given keys.

        :param d: Original dictionary.
        :param keys: Keys to exclude from the result.
        :return: New dictionary without the specified keys.
        """
        return {
            k: v
            for k, v in d.items()
            if k not in keys
        }

    def _enrich_object(
        self,
        obj_schema: dict[str, Any],
        obj_value: Any
    ) -> dict[str, Any]:
        """
        Enrich an object-typed property according to its schema.

        Nested properties are enriched recursively and combined with the
        metadata extracted from the object schema itself.

        :param obj_schema: Schema definition for the object.
        :param obj_value: Current value for the object, expected to be a
                          dictionary or ``None``.
        :return: Enriched object containing metadata and nested fields.
        """
        nested_values = obj_value if isinstance(obj_value, dict) else {}
        nested = self._enrich_properties(obj_schema, nested_values)
        meta = self._meta(obj_schema)
        if nested:
            meta.update(nested)
        return meta

    def _enrich_array(
        self,
        arr_schema: dict[str, Any],
        arr_value: Any
    ) -> dict[str, Any]:
        """
        Enrich an array-typed property according to its schema.

        When no structured value is provided, the method returns a
        metadata dictionary with an empty ``value`` list and without
        the ``items`` key from the schema.

        :param arr_schema: Schema definition for the array.
        :param arr_value: Current value for the array.
        :return: Enriched array representation or an empty dictionary.
        """
        out = {}
        if not isinstance(arr_value, dict):
            out = self._without(arr_schema, "items")
            out["value"] = []
        return out

    def _enrich_named_property(
        self,
        key: str,
        schema: dict[str, Any],
        values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enrich a single named property according to its type.

        Objects and arrays are delegated to their specific helpers,
        while primitive types are wrapped with metadata and a
        ``value`` field.

        :param key: Property name.
        :param schema: Schema definition for the property.
        :param values: Dictionary containing current values for the parent
                       object.
        :return: Enriched representation for the property.
        """
        value = values.get(key, None)
        t = schema.get("type")

        if t == "object":
            return self._enrich_object(schema, value)
        if t == "array":
            return self._enrich_array(schema, value)
        out = self._meta(schema)
        out["value"] = value
        return out

    def _initialize_from_schema(
        self,
        schema: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Build the initial payload from a schema.

        Includes:
        * All fields required by the schema.
        * All fields listed under ``initialize``.
        * Metadata fields defined in the schema.
        * Correctly initialized structures for objects, arrays and leaf nodes.

        :param schema: Fully normalized JSON schema.
        :return: Initial structured payload used to construct a namespace.
        """
        required: set[str] = set(schema.get("required", []))
        initialize: set[str] = set(schema.get("initialize", []))
        fake_values: dict[str, Any] = {}
        result: dict[str, Any] = {}

        for key in required.union(initialize):
            prop_schema = self._find_property_schema(schema, key)
            prop_schema = self._replace_patterns_with_properties(
                prop_schema,
                {}
            )
            result[key] = self._enrich_named_property(
                key,
                prop_schema,
                fake_values
            )
        meta = self._meta(schema)
        meta.update(result)
        return meta

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
        any_of = schema.get("anyOf", [])
        for candidate in any_of:
            cprops = candidate.get("properties", {})
            if key in cprops:
                return cprops[key]
        return None  # pragma: no cover
