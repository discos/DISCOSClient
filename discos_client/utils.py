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


def get_client_auth_keys(identity: str) -> tuple[bytes, bytes]:
    """Retrieve the CURVE client key pair associated with a given identity.

    The key pair is loaded from the user's configuration directory,
    typically located at:
        ``~/.config/discos/rpc/client/<identity>.key_secret``

    :param identity: The name of the client identity (key file prefix).
    :return: A tuple containing the client public and secret keys.
    :raises OSError: If the key file cannot be found or loaded.
    """
    config_base = Path(user_config_dir("discos"))
    curve_directory = config_base / "rpc" / "client"
    client_pair = curve_directory / f"{identity}.key_secret"
    client_public, client_secret = load_certificate(client_pair)
    return client_public, client_secret


def get_server_public_key(
    telescope: str | None = None,
    server_public_key_file: str | Path | None = None,
) -> bytes:
    """Retrieve the CURVE public key of a DISCOS RPC server.

    The server public key can be obtained either from a predefined
    telescope configuration or from an explicit key file.

    Exactly one of the following must be provided:
      - ``telescope``: loads the key from the package resources
        (``discos_client/servers/<telescope>/server.key``)
      - ``server_public_key_file``: loads the key from a user-specified path

    :param telescope: The telescope name used to locate a bundled server key.
    :param server_public_key_file: Path to a server public key file.
    :return: The server public key.
    :raises ValueError: If both or neither arguments are provided.
    :raises OSError: If the key file cannot be found or loaded.
    """
    if telescope is not None and server_public_key_file is not None:
        raise ValueError(
            "Use either 'telescope' or 'server_public_key_file', not both."
        )

    if server_public_key_file is not None:
        server_public, _ = load_certificate(Path(server_public_key_file))
        return server_public

    if telescope is not None:
        server_pair = files("discos_client") / "servers" \
            / telescope.lower() / "server.key"
        server_public, _ = load_certificate(server_pair)
        return server_public

    raise ValueError(
        "Either 'telescope' or 'server_public_key_file' must be provided "
        "to enable RPC."
    )


def get_auth_keys(
    identity: str,
    telescope: str | None = None,
    server_public_key_file: str | Path | None = None
) -> tuple[bytes, bytes, bytes]:
    """Retrieve CURVE authentication keys for both client and server.

    This function loads:
      - the client key pair associated with the given ``identity``
      - the server public key, either from a telescope profile or an
        explicit file

    The server key selection follows these rules:
      - if ``server_public_key_file`` is provided, it is used
      - otherwise, ``telescope`` must be provided to load a bundled key

    :param identity: The name of the client identity (key file prefix).
    :param telescope: The telescope name used to locate a bundled server key.
    :param server_public_key_file: Path to a server public key file.
    :return: A tuple containing (client_public, client_secret, server_public).
    :raises ValueError: If neither or both server key sources are provided.
    :raises OSError: If any key file cannot be found or loaded.
    """
    client_public, client_secret = get_client_auth_keys(identity)
    server_public = get_server_public_key(telescope, server_public_key_file)
    return client_public, client_secret, server_public


def timestamp() -> dict[str, Any]:
    """Return the current timestamp in multiple standard formats.

    The returned dictionary contains:
      - ``unix_time``: seconds since the Unix epoch (float)
      - ``omg_time``: time in 100-nanosecond intervals since
        1582-10-15 (UUID/OMG timestamp format)
      - ``mjd``: Modified Julian Date (days since 1858-11-17)
      - ``iso8601``: UTC time in ISO 8601 format with millisecond precision

    :return: A dictionary containing the current time in multiple formats.
    """
    now = time.time()
    iso8601 = datetime.fromtimestamp(now, tz=timezone.utc)
    iso8601 = iso8601.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "unix_time": now,
        "omg_time": int((now + 12219292800) * 10_000_000),
        "mjd": (now / 86400.0) + 40587.0,
        "iso8601": iso8601
    }
