from __future__ import annotations
import re
import json
import operator
from typing import Any, Callable, TYPE_CHECKING
from importlib.resources import files


if TYPE_CHECKING:  # pragma: no cover
    from .namespace import DISCOSNamespace

__all__ = [
    "delegated_operations",
    "public_dict",
    "SchemaMerger"
]


def delegated_operations(handler: str) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        f = 'add concat floordiv mod mul pow sub truediv'.split()
        r = [f"r{e}" for e in f]
        c = 'eq ge gt le lt ne'.split()
        for op in f + r + c:
            method_name = f"__{op}__"

            def make_method(op_name: str) -> Callable:
                def method(self: Any, other: Any) -> Any:
                    if op_name.startswith('r'):
                        op_func = getattr(operator, op_name[1:])

                        def func(x):
                            return op_func(other, x)
                    else:
                        op_func = getattr(operator, op_name)

                        def func(x):
                            return op_func(x, other)
                    return getattr(self, handler)(func)
                return method
            setattr(cls, method_name, make_method(op))
        return cls
    return decorator


def public_dict(
    obj: DISCOSNamespace,
    is_fn,
    get_value_fn,
    typename: str
) -> Any:
    d = {}
    for k, v in vars(obj).items():
        if k == f"_{typename}__value":
            d.update(__serialize_value(v, is_fn, get_value_fn, typename))
        elif not k.startswith("_"):
            if k == "enum" and is_fn(v):
                d[k] = __unwrap_enum(v, is_fn, get_value_fn)
            else:
                d[k] = public_dict(
                    v,
                    is_fn,
                    get_value_fn,
                    typename
                ) if is_fn(v) else v
    return d


def __serialize_value(
    value: Any,
    is_fn,
    get_value_fn,
    typename: str
) -> dict[str, Any]:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return {"value": value}
    if isinstance(value,  (list, tuple)):
        return {
            "items": [
                public_dict(
                    v,
                    is_fn,
                    get_value_fn,
                    typename
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
        self.schemas, self.definitions = self.__load_schemas(telescope)

    @staticmethod
    def __absolutize_refs(obj, filename):
        if isinstance(obj, dict):
            if "$ref" in obj and obj["$ref"].startswith("#/$defs/"):
                obj["$ref"] = f"{filename}{obj['$ref']}"
            for v in obj.values():
                SchemaMerger.__absolutize_refs(v, filename)
        elif isinstance(obj, list):
            for item in obj:
                SchemaMerger.__absolutize_refs(item, filename)

    def __load_schemas(
        self,
        telescope: str | None
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        base_dir = files("discos_client") / "schemas"
        schemas_dirs = [base_dir / "common"]
        if telescope:
            schemas_dirs.append(base_dir / telescope.lower())
        schemas = {}
        definitions = {}

        definitions_dir = base_dir / "definitions"
        if definitions_dir.exists():
            for f in definitions_dir.iterdir():
                if f.is_file() and f.name.endswith(".json"):
                    schema = json.loads(f.read_text(encoding="utf-8"))
                    self.__absolutize_refs(
                        schema,
                        f.relative_to(base_dir).as_posix()
                    )
                    definitions[
                        f"{f.relative_to(base_dir).as_posix()}"
                    ] = schema
        else:
            raise FileNotFoundError(f"{definitions_dir} not found.")
        for d in schemas_dirs:
            for f in d.iterdir():
                if f.is_file() and f.name.endswith(".json"):
                    key = f.stem
                    schema = json.loads(f.read_text(encoding="utf-8"))
                    self.__absolutize_refs(
                        schema,
                        f.relative_to(base_dir).as_posix()
                    )
                    schemas[key] = schema
                    for k, v in schema.get("$defs", {}).items():
                        definitions[
                            f"{f.relative_to(base_dir).as_posix()}#/$defs/{k}"
                        ] = v
        return schemas, definitions

    def merge_schema(
        self,
        name: str,
        message: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in self.schemas:
            raise ValueError(f"Schema '{name}' was not loaded.")
        schema = self.schemas[name]
        expanded = self.__expand_all_refs(schema)
        enriched = self.__expand_schema_keywords(expanded, message)
        enriched = self.__enrich_properties(
            enriched.get("properties", {}),
            message,
            enriched,
            enriched.get("patternProperties", {})
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
                return self.__expand_all_refs({
                    **resolved,
                    **{k: v for k, v in obj.items() if k != "$ref"}
                })
            return {k: self.__expand_all_refs(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.__expand_all_refs(item) for item in obj]
        return obj

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
        if "oneOf" in obj:
            data = root_schema
            for candidate in obj["oneOf"]:
                props = set(candidate.get("properties", {}).keys())
                patterns = candidate.get("patternProperties", {})
                min_p = candidate.get("minProperties", 0)
                max_p = candidate.get("maxProperties", float("inf"))
                add_ok = candidate.get("additionalProperties", True)
                keys = set(data.keys())
                if not min_p <= len(keys) <= max_p:
                    continue
                if not add_ok and props:
                    if any(k not in props and
                            not any(re.fullmatch(p, k) for p in patterns)
                            for k in keys):
                        continue
                if props and not props.issuperset(keys) and not patterns:
                    continue
                return candidate
            raise ValueError("No matching schema in oneOf")
        return obj

    def __enrich_properties(
        self,
        properties: dict[str, Any],
        values: dict[str, Any],
        root_schema: dict[str, Any],
        pattern_properties: dict[str, Any] = None
    ) -> dict[str, Any]:
        result = {}
        for key, prop_schema in properties.items():
            expanded = self.__expand_schema_keywords(prop_schema, root_schema)
            result[key] = self.__enrich_named_property(
                key,
                expanded,
                values,
                root_schema
            )
        result.update(self.__enrich_pattern_properties(
            pattern_properties or {},
            properties,
            values,
            root_schema)
        )
        return result

    def __enrich_named_property(
        self,
        key: str,
        prop_schema: dict[str, Any],
        values: dict[str, Any],
        root_schema: dict[str, Any]
    ) -> dict[str, Any]:
        prop_schema = self.__expand_schema_keywords(prop_schema, root_schema)
        value = values.get(key, None)
        if prop_schema.get("type") == "object" and "properties" in prop_schema:
            nested_values = value if isinstance(value, dict) else {}
            nested = self.__enrich_properties(
                prop_schema["properties"],
                nested_values,
                root_schema,
                prop_schema.get("patternProperties", {})
            )
            return {
                **{
                    k: v
                    for k, v in prop_schema.items()
                    if k in ("type", "title", "description")
                },
                **nested
            }
        if prop_schema.get("type") == "array":
            item_schema = self.__expand_schema_keywords(
                prop_schema.get("items", {}),
                root_schema
            )
            item_metadata = {
                k: v
                for k, v in item_schema.items()
                if k in ("type", "title", "description")
            }
            return {
                **{k: v for k, v in prop_schema.items() if k != "items"},
                "value": [
                    {
                        **item_metadata,
                        **self.__enrich_properties(
                            item_schema.get("properties", {}),
                            v,
                            root_schema,
                            item_schema.get("patternProperties", {})
                        )
                    } if isinstance(v, dict) else {"value": v}
                    for v in value
                ] if isinstance(value, list) else []
            }
        enriched = dict(prop_schema)
        enriched["value"] = value
        return enriched

    def __enrich_pattern_properties(
        self,
        pattern_properties: dict[str, Any],
        defined_properties: dict[str, Any],
        values: dict[str, Any],
        root_schema: dict[str, Any]
    ) -> dict[str, Any]:
        result = {}
        for pattern, pattern_schema in pattern_properties.items():
            regex = re.compile(pattern)
            for key in values:
                if key in defined_properties or not regex.match(key):
                    continue
                schema = self.__expand_schema_keywords(
                    pattern_schema,
                    root_schema
                )
                value = values[key]
                if schema.get("type") == "object" and "properties" in schema:
                    nested_values = value if isinstance(value, dict) else {}
                    nested = self.__enrich_properties(
                        schema["properties"],
                        nested_values,
                        root_schema,
                        schema.get("patternProperties", {})
                    )
                    enriched = {
                        **{
                            k: v for k, v in schema.items()
                            if k in ("type", "title", "description")
                        },
                        **nested
                    }
                else:
                    enriched = dict(schema)
                    enriched["value"] = value
                result[key] = enriched
        return result

    def get_topics(self) -> list[str]:
        return list(self.schemas.keys())
