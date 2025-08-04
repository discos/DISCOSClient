from __future__ import annotations
import re
import json
import operator
from pathlib import Path
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
    if not is_fn(obj):
        return obj
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
        self.schemas, self.definitions, self.node_to_id = \
            self.__load_schemas(telescope)
        for schema_id, schema in self.schemas.items():
            self.schemas[schema_id] = self.__expand_all_refs(schema)

    def __normalize_ref__(self, ref: str, current_file: Path) -> str:
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

    def __absolutize_refs(self, obj: dict | list, filename: str):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                obj["$ref"] = self.__normalize_ref__(ref, Path(filename))
            for v in obj.values():
                self.__absolutize_refs(v, filename)
        elif isinstance(obj, list):
            for item in obj:
                self.__absolutize_refs(item, filename)

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

    def merge_schema(
        self,
        name: str,
        message: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in self.node_to_id:
            raise ValueError(f"Schema '{name}' was not loaded.")
        name = self.node_to_id[name]
        schema = self.schemas[name]
        expanded = self.__expand_all_refs(schema)
        enriched = self.__expand_schema_keywords(expanded, message)
        enriched = self.__enrich_properties(
            enriched,
            message,
        )
        return {
            **{
                k: v
                for k, v in enriched.items()
                if k in ("title", "type", "description")
            },
            **enriched
        }

    def __expand_all_refs(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                resolved = self.definitions.get(ref)
                if not resolved:
                    raise ValueError(f"Unresolved $ref: {ref}")
                return self.__expand_all_refs(
                    {
                        **resolved,
                        **{k: v for k, v in obj.items() if k != "$ref"}
                    }
                )
            return {
                k: self.__expand_all_refs(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self.__expand_all_refs(item) for item in obj]
        return obj

    @staticmethod
    def __match_candidate__(data, candidate):
        props = set(candidate.get("properties", {}).keys())
        patterns = candidate.get("patternProperties", {})
        min_p = candidate.get("minProperties", 0)
        max_p = candidate.get("maxProperties", float("inf"))
        add_ok = candidate.get("additionalProperties", True)
        keys = set(data.keys())

        if not min_p <= len(keys) <= max_p:
            return False
        if not add_ok and props:
            if any(k not in props and
                   not any(re.fullmatch(p, k) for p in patterns)
                   for k in keys):
                return False
        if props and not props.issuperset(keys) and not patterns:
            return False
        return True

    def __expand_schema_keywords(
        self,
        obj: dict[str, Any],
        root_schema: dict[str, Any]
    ) -> dict[str, Any]:
        if "allOf" in obj:
            result = {}
            for item in obj["allOf"]:
                result.update(item)
            return {**result, **{k: v for k, v in obj.items() if k != "allOf"}}
        if "anyOf" in obj:
            data = root_schema
            merged = {}
            for candidate in obj["anyOf"]:
                if self.__match_candidate__(data, candidate):
                    merged.update(candidate)
            if merged:
                return {
                    **merged, **{k: v for k, v in obj.items() if k != "anyOf"}
                }
        if "oneOf" in obj:
            data = root_schema
            for candidate in obj["oneOf"]:
                if self.__match_candidate__(data, candidate):
                    return candidate
            raise ValueError("No matching schema in oneOf")
        return obj

    def __enrich_properties(
        self,
        schema: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        result = {}
        for key, prop_schema in properties.items():
            if key in required or key in values:
                result[key] = self.__enrich_named_property(
                    key,
                    self.__expand_schema_keywords(prop_schema, schema),
                    values
                )
        result.update(self.__enrich_pattern_properties(
            schema,
            values
        ))
        return result

    def __enrich_named_property(
        self,
        key: str,
        schema: dict[str, Any],
        values: dict[str, Any]
    ) -> dict[str, Any]:
        value = values.get(key, None)
        if schema.get("type") == "object" and "properties" in schema:
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

    def __enrich_pattern_properties(
        self,
        schema: dict[str, Any],
        values: dict[str, Any]
    ) -> dict[str, Any]:
        result = {}
        pattern_properties = schema.get("patternProperties", {})
        defined_properties = schema.get("properties", {})
        for pattern, pattern_schema in pattern_properties.items():
            regex = re.compile(pattern)
            for key, _ in values.items():
                if key in defined_properties or not regex.match(key):
                    continue
                result[key] = self.__enrich_named_property(
                    key, pattern_schema, values
                )
        return result

    def get_topics(self) -> list[str]:
        return list(self.node_to_id.keys())
