from __future__ import annotations
import json
import operator
from typing import Any, Callable
from importlib.resources import files
from pathlib import Path

__all__ = [
    "delegated_operations",
    "load_schemas",
    "merge_schema",
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


def load_schemas() -> dict[str, dict]:
    schemas_dir = files("discos_client") / "schemas"
    schemas = {
        Path(f.name).stem: json.loads(f.read_text())
        for f in schemas_dir.iterdir()
        if f.is_file()
    }
    return schemas


def merge_schema(
    schema: dict[str, Any],
    message: dict[str, Any]
) -> dict[str, Any]:
    return __enrich_properties(schema["properties"], message, schema)


def __enrich_properties(
    properties: dict[str, Any],
    values: dict[str, Any],
    root_schema: dict[str, Any]
) -> dict[str, Any]:
    result = {}
    for key, value in values.items():
        prop_schema = __expand_allof(properties.get(key, {}), root_schema)
        if "$ref" in prop_schema:
            prop_schema = __resolve_ref(prop_schema["$ref"], root_schema)
        if isinstance(value, dict) and \
                prop_schema.get("type") == "object" and \
                "properties" in prop_schema:
            nested = __enrich_properties(
                prop_schema["properties"],
                value,
                root_schema
            )
            enriched = {
                k: v for k, v in prop_schema.items()
                if k not in ("properties", "required")
            }
            enriched.update(nested)
        elif isinstance(value, list) and \
                prop_schema.get("type") == "array":
            item_schema = prop_schema.get("items", {})
            if "$ref" in item_schema:
                item_schema = __resolve_ref(item_schema["$ref"], root_schema)
            enriched = dict(prop_schema)
            enriched["items"] = [
                __enrich_properties(
                    item_schema.get("properties", {}), v, root_schema
                )
                if isinstance(v, dict) else {"value": v}
                for v in value
            ]
        else:
            enriched = dict(prop_schema)
            enriched["value"] = value
        result[key] = enriched
    return result


def __expand_allof(
    obj: dict[str, Any],
    root_schema: dict[str, Any]
) -> dict[str, Any]:
    if "allOf" in obj:
        result = {}
        for item in obj["allOf"]:
            if "$ref" in item:
                result.update(__resolve_ref(item["$ref"], root_schema))
            else:
                result.update(item)
        return {**result, **{k: v for k, v in obj.items() if k != "allOf"}}
    return obj


def __resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if ref.startswith("#/$defs/"):
        def_key = ref.split("/")[-1]
        return root_schema.get("$defs", {}).get(def_key, {})
    raise ValueError(f"Unsupported $ref format: {ref}")
