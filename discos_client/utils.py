from __future__ import annotations
import operator
import secrets
import string
from typing import Any, Callable


META_KEYS = ("type", "title", "description", "format", "unit", "enum")

__all__ = [
    "rand_id",
    "delegated_operations",
    "delegated_comparisons",
    "public_dict"
]


def rand_id():
    _id = "".join(
        secrets.choice(string.digits + string.ascii_letters) for _ in range(4)
    )

    return f"{_id}_"


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
    obj: Any,
    is_fn: Callable,
    get_value_fn: Callable
) -> Any:
    d = {}
    for k, v in vars(obj).items():
        if k == "_value":
            if is_fn(v):
                d["items"] = __unwrap(v, is_fn, get_value_fn)
            else:
                d["value"] = __serialize_value(v, is_fn, get_value_fn)
        elif not k.startswith("_"):
            if k == "enum" and is_fn(v):
                d[k] = __unwrap(v, is_fn, get_value_fn)
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
    if isinstance(value, (list, tuple)):
        return [
            public_dict(
                v,
                is_fn,
                get_value_fn
            ) for v in value
        ]
    return value


def __unwrap(value: Any, is_fn, get_value_fn) -> Any:
    while is_fn(value):
        value = get_value_fn(value)
    return list(value) if isinstance(value, (list, tuple)) else value
