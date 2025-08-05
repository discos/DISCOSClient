from __future__ import annotations
import re
import json
import operator
from pathlib import Path
from copy import deepcopy
from typing import Any, Callable, TYPE_CHECKING
from importlib.resources import files


if TYPE_CHECKING:  # pragma: no cover
    from .namespace import DISCOSNamespace

__all__ = [
    "delegated_operations",
    "delegated_comparisons",
    "public_dict",
    "SchemaMerger"
]


def delegated_operations(handler: str) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        ops = 'add concat floordiv mod mul pow sub truediv'.split()
        ops += [f"r{op}" for op in ops]

        for op in ops:
            method_name = f"__{op}__"
            is_reflective = op.startswith("r")
            op = op[1:] if is_reflective else op
            op_func = getattr(operator, op)

            def method(
                self: Any,
                other: Any,
                op_func=op_func,
                is_reflective=is_reflective
            ) -> Any:
                return getattr(self, handler)(
                    lambda x: op_func(other, x)
                    if is_reflective
                    else op_func(x, other)
                )

            setattr(cls, method_name, method)

        return cls
    return decorator


def delegated_comparisons(handler: str) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        comparisons = 'eq ge gt le lt ne'.split()
        for op in comparisons:
            method_name = f"__{op}__"
            op_func = getattr(operator, op)

            def method(
                self: Any,
                other: Any,
                op_func=op_func
            ) -> Any:
                return getattr(self, handler)(op_func, other)

            setattr(cls, method_name, method)
        return cls
    return decorator


def public_dict(
    obj: DISCOSNamespace,
    is_fn,
    get_value_fn
) -> Any:
    d = {}
    for k, v in vars(obj).items():
        if k == "_value":
            d.update(__serialize_value(v, is_fn, get_value_fn))
        elif not k.startswith("_"):
            if k == "enum" and is_fn(v):
                d[k] = __unwrap_enum(v, is_fn, get_value_fn)
            else:
                d[k] = public_dict(
                    v,
                    is_fn,
                    get_value_fn
                ) if is_fn(v) else v
    return d


def __serialize_value(
    value: Any,
    is_fn,
    get_value_fn
) -> dict[str, Any]:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return {"value": value}
    if isinstance(value,  (list, tuple)):
        return {
            "items": [
                public_dict(
                    v,
                    is_fn,
                    get_value_fn
                ) for v in value
            ]
        }
    return {"value": value}


def __unwrap_enum(value: Any, is_fn, get_value_fn) -> Any:
    while is_fn(value):
        value = get_value_fn(value)
    return list(value) if isinstance(value, (list, tuple)) else value


class SchemaMerger:
    def __init__(self, telescope: str | None):
        self.base_dir = files("discos_client") / "schemas"
        self.schemas, definitions, self.node_to_id = \
            self.__load_schemas(telescope)

        for def_id, definition in definitions.items():
            definition = self.__absolutize_refs(definition, def_id)
            definition = self.__expand_refs(definition, definitions)
            definition = self.__merge_all_of(definition)
            definitions[def_id] = definition

        for schema_id, schema in self.schemas.items():
            schema = self.__absolutize_refs(schema, schema_id)
            schema = self.__expand_refs(schema, definitions)
            schema = self.__merge_all_of(schema)
            schema.pop("$defs", None)
            self.schemas[schema_id] = schema

    def merge_schema(
        self,
        name: str,
        message: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in self.node_to_id:
            raise ValueError(f"Schema '{name}' was not loaded.")
        name = self.node_to_id[name]
        schema = self.schemas[name]
        enriched = self.__enrich_properties(schema, message)
        return {
            **{
                k: v
                for k, v in enriched.items()
                if k in ("title", "type", "description")
            },
            **enriched
        }

    def __load_schemas(
        self,
        telescope: str | None
    ) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
        schemas_dirs = [self.base_dir / "common"]
        if telescope:
            schemas_dirs.append(self.base_dir / telescope.lower())
        schemas: dict[str, dict] = {}
        definitions: dict[str, dict] = {}
        node_to_id: dict[str, dict] = {}
        definitions_dir = self.base_dir / "definitions"
        if not definitions_dir.exists():
            raise FileNotFoundError(f"{definitions_dir} not found")
        for f in definitions_dir.iterdir():
            if f.is_file() and f.name.endswith(".json"):
                rel_path = f.resolve().relative_to(self.base_dir).as_posix()
                schema = json.loads(f.read_text(encoding="utf-8"))
                self.__absolutize_refs(schema, rel_path)
                schema_id = schema.get("$id", rel_path)
                definitions[schema_id] = schema
        for d in schemas_dirs:
            for f in d.iterdir():
                if f.is_file() and f.name.endswith(".json"):
                    rel_path = \
                        f.resolve().relative_to(self.base_dir).as_posix()
                    schema = json.loads(f.read_text(encoding="utf-8"))
                    self.__absolutize_refs(schema, rel_path)
                    schema_id = schema.get("$id", rel_path)
                    node_name = schema.get("node")
                    if not node_name:
                        raise ValueError(f"Missing 'node' field in {rel_path}")
                    node_to_id[node_name] = schema_id
                    schemas[schema_id] = schema
                    for k, v in schema.get("$defs", {}).items():
                        definitions[f"{schema_id}#/$defs/{k}"] = v
        return schemas, definitions, node_to_id

    def __absolutize_refs(
        self,
        schema: dict[str, Any],
        current_file: str
    ) -> dict[str, Any]:
        def recurse(obj: Any):
            if isinstance(obj, dict):
                if "$ref" in obj:
                    obj["$ref"] = self.__normalize_ref(
                        obj["$ref"],
                        Path(current_file)
                    )
                for v in obj.values():
                    recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)
        recurse(schema)
        return schema

    def __normalize_ref(self, ref: str, current_file: Path) -> str:
        if ref.startswith("#"):
            return f"{current_file.as_posix()}{ref}"
        base_dir = self.base_dir
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
        return f"{result}#{fragment}" if fragment else result.as_posix()

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
                    if not resolved:
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
            for k in keys:
                if k not in props \
                        and not any(re.fullmatch(p, k) for p in patterns):
                    return None
        required = set(candidate.get("required", []))
        if not required.issubset(keys):
            return None
        common_keys = len(keys & props)
        pattern_matches = sum(
            1 for k in keys for p in patterns if re.fullmatch(p, k)
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
        schema_copy = deepcopy(schema)
        pattern_props = schema_copy.pop("patternProperties", None)
        if not pattern_props:
            return schema_copy
        schema_copy.setdefault("properties", {})
        for msg_key in message.keys():
            for pattern, pattern_schema in pattern_props.items():
                if re.fullmatch(pattern, msg_key):
                    schema_copy["properties"][msg_key] = pattern_schema
        return schema_copy

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
                prop_schema = self.__expand_schema_keywords(
                    prop_schema, schema
                )
                prop_schema = self.__replace_patterns_with_properties(
                    prop_schema, values.get(key, {})
                )
                result[key] = self.__enrich_named_property(
                    key, prop_schema, values
                )
        return result

    def __enrich_named_property(
        self,
        key: str,
        schema: dict[str, Any],
        values: dict[str, Any]
    ) -> dict[str, Any]:
        schema = self.__expand_schema_keywords(schema, values)
        value = values.get(key, None)
        if schema.get("type") == "object":
            nested_values = value if isinstance(value, dict) else {}
            nested = self.__enrich_properties(schema, nested_values)
            return {
                **{
                    k: v
                    for k, v in schema.items()
                    if k in ("type", "title", "description")
                },
                **nested
            }
        if schema.get("type") == "array":
            item_schema = schema.get("items", {})
            item_metadata = {
                k: v
                for k, v in item_schema.items()
                if k in ("type", "title", "description")
            }
            return {
                **{k: v for k, v in schema.items() if k != "items"},
                "value": [
                    {
                        **item_metadata,
                        **self.__enrich_properties(item_schema, v)
                    }
                    if isinstance(v, dict) else {"value": v}
                    for v in value
                ] if isinstance(value, list) else []
            }
        enriched = dict(schema)
        enriched["value"] = value
        return enriched

    def get_topics(self) -> list[str]:
        return list(self.node_to_id.keys())
