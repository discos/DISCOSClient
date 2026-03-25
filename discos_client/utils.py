from __future__ import annotations
import operator
import secrets
import string
import time
from datetime import datetime, timezone
from typing import Any, Callable
from importlib.resources import files
from pathlib import Path
from zmq.auth import load_certificate
from platformdirs import user_config_dir


__all__ = [
    "META_KEYS",
    "rand_id",
    "delegated_operations",
    "delegated_comparisons",
    "public_dict",
    "get_auth_keys",
    "timestamp"
]

META_KEYS = ("type", "title", "description", "format", "unit", "enum")


def rand_id():
    """
    Creates a random ID string for a caller.

    The returned ID has the form ``[0-9A-Za-z]{4}_``:
    four random alphanumeric characters followed by an underscore.

    :return: The random ID string.
    """
    _id = "".join(
        secrets.choice(string.digits + string.ascii_letters) for _ in range(4)
    )

    return f"{_id}_"


def delegated_operations(handler: str) -> Callable[[type], type]:
    """
    Returns a decorator which enables a class to use some python operations
    such as "add", "concat", etc.

    :param handler: The name of the method which will be used to perform the
                    operation.
    :return: The decorator for a class.
    """
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
    """
    Returns a decorator which enables a class to use some python comparisons
    operators such as "eq", "ge", "gt", etc.

    :param handler: The name of the method which will be used to perform the
                    comparison.
    :return: The decorator for a class.
    """
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
    """
    Returns a copy of the dictionary containing only the public attributes of
    the given object.

    :param obj: The object which a public dictionary will be returned.
    :param is_fn: A function that checks if the given object is instance of a
                  given type.
    :param get_value_fn: A function that returns the inner value of the object.
    :return: The dictionary containing only the public values of the object.
    """
    d = {}
    for k, v in vars(obj).items():
        if callable(v):
            # We don't need to include methods
            continue
        if k == "_value":
            if isinstance(v, (list, tuple)):
                d["items"] = __unwrap(v, is_fn, get_value_fn)
            else:
                d["value"] = v
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


def __unwrap(value: Any, is_fn, get_value_fn) -> Any:
    """
    Returns the inner value of a given object, either in its original form or
    as a list.

    :param value: The object whose internal value will be returned.
    :param is_fn: A function that checks if the given object is instance of a
                  given type.
    :param get_value_fn: A function that returns the inner value of the object.
    :return: The internal value if present, either as its original type or as a
             list, or value itself.
    """
    while is_fn(value):
        value = get_value_fn(value)
    return list(value) if isinstance(value, (list, tuple)) else value


def get_auth_keys(
    telescope: str,
    identity: str
) -> tuple[bytes]:
    """Retrieves the CURVE authentication keys, both for the client and
    the desired server.

    :param telescope: The telescope for which the server public key will be
                      retrieved.
    :param identity: The name of the key pair file to be used.
    :return: The client's public and secret keys, followed by the server's
             public key, as a tuple.
    """
    config_base = Path(user_config_dir("discos"))
    curve_directory = config_base / "rpc" / "client"
    client_pair = curve_directory / f"{identity}.key_secret"
    server_pair = files("discos_client") / "servers" \
        / telescope.lower() / "server.key"
    client_public, client_secret = load_certificate(client_pair)
    server_public, _ = load_certificate(server_pair)
    return client_public, client_secret, server_public


def timestamp() -> dict[str, Any]:
    now = time.time()
    iso8601 = datetime.fromtimestamp(now, tz=timezone.utc)
    iso8601 = iso8601.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "unix_time": now,
        "omg_time": int((now + 12219292800) * 10_000_000),
        "mjd": (now / 86400.0) + 40587.0,
        "iso8601": iso8601
    }
