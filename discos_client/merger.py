from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Any
from importlib.resources import files
from collections.abc import Iterable


META_KEYS = ("type", "title", "description", "format", "unit", "enum")

__all__ = [
    "SchemaMerger",
]


class SchemaMerger:
    _instance: SchemaMerger | None = None

    def __init__(self, telescope: str | None = None):
        base_dir = files("discos_client") / "schemas"
        self._pp_cache: \
            dict[int, list[tuple[str, "re.Pattern", str, dict]]] = {}
        self.schemas, definitions, self.node_to_id = \
            self.__load_schemas(base_dir, telescope)

        for def_id, definition in definitions.items():
            definition = self.__absolutize_refs(definition, base_dir, def_id)
            definition = self.__expand_refs(definition, definitions)
            definition = self.__merge_all_of(definition)
            self.__precompile_patternprops(definition)
            definitions[def_id] = definition

        for schema_id, schema in self.schemas.items():
            schema = self.__absolutize_refs(schema, base_dir, schema_id)
            schema = self.__expand_refs(schema, definitions)
            schema = self.__merge_all_of(schema)
            schema.pop("$defs", None)
            self.__precompile_patternprops(schema)
            self.schemas[schema_id] = schema

    def merge_schema(
        self,
        name: str,
        message: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in self.node_to_id:  # pragma: no cover
            raise ValueError(f"Schema '{name}' was not loaded.")
        name = self.node_to_id[name]
        schema = self.schemas[name]
        return self._enrich_object(schema, message)

    def _literal_prefix(self, pat: str) -> str:
        i = 0
        if pat.startswith('^'):
            i = 1
        out = []
        meta = set('.^$*+?[]{}()|\\')
        while i < len(pat):
            c = pat[i]
            if c in meta:
                break
            out.append(c)
            i += 1
        return ''.join(out)

    def __precompile_patternprops(self, obj: dict | list) -> None:
        for d in self.__walk_dicts(obj):
            pp = d.get("patternProperties")
            if not isinstance(pp, dict) or not pp:
                continue
            key = id(pp)
            if key not in self._pp_cache:
                self._pp_cache[key] = self.__build_pp_list(pp)

    def __walk_dicts(self, root: dict | list) -> Iterable[dict]:
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

    def __build_pp_list(
        self,
        pp: dict
    ) -> list[tuple[str, re.Pattern | None, str, dict]]:
        compiled: list[tuple[str, re.Pattern | None, str, dict]] = []
        for pat, pschema in pp.items():
            try:
                rx = re.compile(pat)
            except re.error:  # pragma: no cover
                rx = None
            pref = self._literal_prefix(pat)
            compiled.append((pat, rx, pref, pschema))
        return compiled

    def __load_schemas(
        self,
        base_dir: Path,
        telescope: str | None
    ) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
        schemas_dirs = [base_dir / "common"]
        if telescope:
            schemas_dirs.append(base_dir / telescope.lower())
        schemas: dict[str, dict] = {}
        definitions: dict[str, dict] = {}
        node_to_id: dict[str, dict] = {}
        definitions_dir = base_dir / "definitions"
        if not definitions_dir.exists():  # pragma: no cover
            raise FileNotFoundError(f"{definitions_dir} not found")
        for f in definitions_dir.iterdir():
            if f.is_file() and f.name.endswith(".json"):
                rel_path = f.resolve().relative_to(base_dir).as_posix()
                schema = json.loads(f.read_text(encoding="utf-8"))
                self.__absolutize_refs(schema, base_dir, rel_path)
                schema_id = schema.get("$id", rel_path)
                definitions[schema_id] = schema
        for d in schemas_dirs:
            for f in d.iterdir():
                if f.is_file() and f.name.endswith(".json"):
                    rel_path = \
                        f.resolve().relative_to(base_dir).as_posix()
                    schema = json.loads(f.read_text(encoding="utf-8"))
                    self.__absolutize_refs(schema, base_dir, rel_path)
                    schema_id = schema.get("$id", rel_path)
                    node_name = schema.get("node")
                    if not node_name:  # pragma: no cover
                        raise ValueError(f"Missing 'node' field in {rel_path}")
                    node_to_id[node_name] = schema_id
                    schemas[schema_id] = schema
                    for k, v in schema.get("$defs", {}).items():
                        definitions[f"{schema_id}#/$defs/{k}"] = v
        return schemas, definitions, node_to_id

    def __absolutize_refs(
        self,
        schema: dict[str, Any],
        base_dir: Path,
        current_file: str
    ) -> dict[str, Any]:
        def recurse(obj: Any):
            if isinstance(obj, dict):
                if "$ref" in obj:
                    obj["$ref"] = self.__normalize_ref(
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

    def __normalize_ref(
        self,
        ref: str,
        base_dir: Path,
        current_file: Path
    ) -> str:
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

    def __expand_refs(
        self,
        schema: dict[str, Any],
        definitions: dict[str, Any]
    ) -> dict[str, Any]:
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

    def __merge_all_of(self, schema: dict[str, Any]) -> dict[str, Any]:
        def recurse(obj: Any):
            if isinstance(obj, dict):
                if "allOf" in obj:
                    merged = self._merge_subschemas(obj["allOf"])
                    merged = self._merge_with_parent(obj, merged)
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
        merged: dict[str, Any] = {}
        required_fields: set[str] = set()
        for subschema in subschemas:
            subschema = self.__merge_all_of(subschema)
            merged.setdefault("properties", {}).update(
                subschema.get("properties", {})
            )
            merged.setdefault("patternProperties", {}).update(
                subschema.get("patternProperties", {})
            )
            required_fields.update(subschema.get("required", []))
            for k, v in subschema.items():
                if k not in ("properties", "patternProperties",
                             "required", "allOf"):
                    merged[k] = v
        if required_fields:
            merged["required"] = list(required_fields)

        return merged

    def _merge_with_parent(
        self,
        obj: dict[str, Any],
        merged: dict[str, Any]
    ) -> dict[str, Any]:
        required_fields = set(merged.get("required", []))
        for k, v in obj.items():
            if k == "required":
                required_fields.update(v)
                merged["required"] = list(required_fields)
            elif k == "properties":
                merged.setdefault("properties", {}).update(v)
            elif k == "patternProperties":
                merged.setdefault("patternProperties", {}).update(v)
            elif k != "allOf":
                merged[k] = v
        return merged

    def __score_candidate(
        self,
        message: dict[str, Any],
        candidate: dict[str, Any]
    ) -> int | None:
        props = set(candidate.get("properties", {}).keys())
        patterns = candidate.get("patternProperties", {})
        min_p = candidate.get("minProperties", 0)
        max_p = candidate.get("maxProperties", float("inf"))
        add_ok = candidate.get("additionalProperties", True)
        keys = set(message.keys())
        if not min_p <= len(keys) <= max_p:
            return None
        if not add_ok:
            comp = self._pp_cache.get(id(patterns)) or []
            for k in keys:
                if k in props:
                    continue
                if not any(rx.fullmatch(k) for _, rx, _, _ in comp):
                    return None
        required = set(candidate.get("required", []))
        if not required.issubset(keys):
            return None
        common_keys = len(keys & props)
        comp = self._pp_cache.get(id(patterns)) or []
        pattern_matches = sum(
            1 for k in keys for _, rx, _, _ in comp if rx.fullmatch(k)
        )
        return common_keys + pattern_matches

    def __expand_schema_keywords(
        self,
        obj: dict[str, Any],
        message: dict[str, Any]
    ) -> dict[str, Any]:
        if "anyOf" in obj:
            best_score = -1
            best_candidate = None
            for candidate in obj["anyOf"]:
                score = self.__score_candidate(message, candidate)
                if score is not None and score > best_score:
                    best_score = score
                    best_candidate = candidate
            if best_candidate:
                return {
                    **best_candidate,
                    **{k: v for k, v in obj.items() if k != "anyOf"}
                }
            return {}
        return obj

    def __replace_patterns_with_properties(
        self,
        schema: dict[str, Any],
        message: dict[str, Any]
    ) -> dict[str, Any]:
        pp = schema.get("patternProperties")
        if not pp or not message:
            if "patternProperties" in schema:
                out = dict(schema)
                out.pop("patternProperties", None)
                return out
            return schema

        compiled = self._pp_cache.get(id(pp), [])
        out = dict(schema)
        out.pop("patternProperties", None)

        props = out.get("properties")
        props_is_copy = False

        for key in message.keys():
            for _, rx, pref, pschema in compiled:
                if pref and not key.startswith(pref):
                    continue
                if rx.fullmatch(key):
                    if not props_is_copy:
                        props = dict(props) if isinstance(props, dict) else {}
                        out["properties"] = props
                        props_is_copy = True
                    props[key] = pschema

        return out

    def __enrich_properties(
        self,
        schema: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        schema = self.__expand_schema_keywords(schema, values)
        schema = self.__replace_patterns_with_properties(schema, values)
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        result = {}
        for key, prop_schema in properties.items():
            if key in required or key in values:
                prop_value = values.get(key, {})
                prop_schema = self.__expand_schema_keywords(
                    prop_schema,
                    prop_value if isinstance(prop_value, dict) else {}
                )
                prop_schema = self.__replace_patterns_with_properties(
                    prop_schema,
                    values.get(key, {})
                )
                result[key] = self.__enrich_named_property(
                    key, prop_schema, values
                )
        return result

    def _meta(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            k: d[k]
            for k in META_KEYS
            if k in d
        }

    def _without(self, d: dict[str, Any], *keys: str) -> dict[str, Any]:
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
        required = obj_schema.get("required", ())
        if obj_value is None and not required:
            return self._meta(obj_schema)
        nested_values = obj_value if isinstance(obj_value, dict) else {}
        nested = self.__enrich_properties(obj_schema, nested_values)
        meta = self._meta(obj_schema)
        if nested:
            meta.update(nested)
        return meta

    def _enrich_array(
        self,
        arr_schema: dict[str, Any],
        arr_value: Any
    ) -> dict[str, Any]:
        if not isinstance(arr_value, list):
            out = self._without(arr_schema, "items")
            out["value"] = []
            return out
        item_schema = arr_schema.get("items") or {}
        out_list: list[dict[str, Any]] = []
        for v in arr_value:
            out_list.append(
                self._enrich_object(item_schema, v)
            )
        out = self._without(arr_schema, "items")
        out["value"] = out_list
        return out

    def __enrich_named_property(
        self,
        key: str,
        schema: dict[str, Any],
        values: dict[str, Any]
    ) -> dict[str, Any]:
        value = values.get(key, None)
        t = schema.get("type")

        if t == "object":
            return self._enrich_object(schema, value)
        if t == "array":
            return self._enrich_array(schema, value)
        out = self._meta(schema)
        out["value"] = value
        return out

    def get_topics(self) -> list[str]:
        return list(self.node_to_id.keys())

    @staticmethod
    def get_instance(telescope: str | None = None):
        if SchemaMerger._instance is None:
            SchemaMerger._instance = SchemaMerger(telescope)
        return SchemaMerger._instance
