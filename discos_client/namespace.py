from __future__ import annotations
import json
from copy import deepcopy
from typing import Any, Callable, Iterator
from .utils import delegated_operations


@delegated_operations('__value_operation__')
class DISCOSNamespace:

    __typename__ = "DISCOSNamespace"

    def __init__(self, **kwargs: Any) -> None:
        def transform(value: Any) -> Any:
            if isinstance(value, dict):
                return DISCOSNamespace(**value)
            if isinstance(value, list):
                value = DISCOSNamespace(
                    value=tuple(transform(v) for v in value)
                )
                return value
            return value

        for k, v in list(kwargs.items()):
            if k in ["items", "value"]:
                del kwargs[k]
                k = "_DISCOSNamespace__value"
            kwargs[k] = transform(v)
        self.__dict__.update(kwargs)

    def __value_operation__(self, operation: Callable[[Any], Any]) -> Any:
        if self.__has_value__(self) and \
                not DISCOSNamespace.__is__(self.__get_value__(self)):
            return operation(self.__get_value__(self))
        raise TypeError(
            f"{self.__typename__} supports operations "
            "only when holding a primitive value"
        )

    def __repr__(self) -> str:
        if self.__has_value__(self):
            return repr(self.__get_value__(self))
        return f"<{self.__typename__}({self.__value_repr__(self)})>"

    def __str__(self) -> str:
        if self.__has_value__(self):
            return str(self.__get_value__(self))
        return format(self, "2i")

    def __int__(self) -> int:
        if self.__has_value__(self):
            return int(self.__get_value__(self))
        raise TypeError(
            f"{self.__typename__} object cannot be converted to int"
        )

    def __float__(self) -> float:
        if self.__has_value__(self):
            return float(self.__get_value__(self))
        raise TypeError(
            f"{self.__typename__} object cannot be converted to float"
        )

    def __neg__(self) -> Any:
        if self.__has_value__(self):
            return -self.__get_value__(self)
        raise TypeError(
            f"{self.__typename__} object cannot be negated"
        )

    def __bool__(self) -> bool:
        if self.__has_value__(self):
            return bool(self.__get_value__(self))
        raise TypeError(
            f"{self.__typename__} object cannot be converted to bool"
        )

    def __getitem__(self, item: Any) -> Any:
        if self.__has_value__(self):
            return self.__get_value__(self)[item]
        raise TypeError(f"{self.__typename__} object is not subscriptable")

    def __len__(self) -> int:
        if self.__has_value__(self):
            return len(self.__get_value__(self))
        raise TypeError(f"{self.__typename__} object has no length")

    def __iter__(self) -> Iterator[Any]:
        if self.__has_value__(self):
            return iter(self.__get_value__(self))
        raise TypeError(f"{self.__typename__} object is not iterable")

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            f"{self.__typename__} is read-only and "
            "does not allow attribute assignment"
        )

    def __delattr__(self, name: str) -> None:
        raise TypeError(
            f"{self.__typename__} is read-only and "
            "does not allow attribute deletion"
        )

    def __ilshift__(self, other: Any) -> DISCOSNamespace:
        for k, ov in vars(other).items():
            if k.startswith("_") and k != f"_{self.__typename__}__value":
                continue
            sv = getattr(self, k, None)
            if DISCOSNamespace.__is__(sv) and DISCOSNamespace.__is__(ov):
                sv <<= ov
            else:
                object.__setattr__(self, k, deepcopy(ov))
        return self

    def __format__(self, spec: str) -> str:
        """
        Custom format method.

        :param spec: The format specifier. It can be:
                     - any format specifier for the inner value object
                     - 'c' for compact JSON representation
                     - 'i' for multi-line, indented JSON representation.
                       'i' can be preceeded by a number, which will be the
                       desired indentation. Default is 2.
        :return str: A JSON formatted string for a non-value container or
                     a formatted str for the inner value.
        """
        if self.__has_value__(self):
            return format(self.__get_value__(self), spec)
        if not spec:
            return str(self)

        indent = None
        separators = None

        fmt_type = spec[-1]
        fmt_param = spec[:-1]

        if fmt_type == "i":
            indent = 2
            if fmt_param:
                try:
                    indent = int(spec[:-1])
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid indent in format spec: '{fmt_param}'"
                    ) from exc
                if indent <= 0:
                    raise ValueError("Indentation must be a positive integer")
        elif fmt_type == "c":
            if fmt_param:
                raise ValueError(
                    "Compact format 'c' does not accept any parameter"
                )
            separators = (",", ":")
        else:
            raise ValueError(
                f"Unknown format code '{spec}' for {self.__typename__}"
            )
        return json.dumps(
            self,
            default=self.__public_dict__,
            indent=indent,
            separators=separators
        )

    def __deepcopy__(self, memo):
        cls = self.__class__
        public = cls.__public_dict__(self)
        copied = deepcopy(public, memo)
        return cls(**copied)

    @classmethod
    def __get_value__(cls, obj: DISCOSNamespace) -> Any:
        value = object.__getattribute__(obj, f"_{cls.__typename__}__value")
        if isinstance(value, tuple):
            value = list(value)
        return value

    @classmethod
    def __has_value__(cls, obj: Any) -> bool:
        return hasattr(obj, f"_{cls.__typename__}__value")

    @classmethod
    def __is__(cls, obj: Any) -> bool:
        return isinstance(obj, cls)

    @classmethod
    def __public_dict__(cls, obj: DISCOSNamespace) -> dict[str, Any]:
        public_dict = {}
        for k, v in vars(obj).items():
            if k == f"_{cls.__typename__}__value":
                key = "items" if isinstance(v, tuple) else "value"
                public_dict[key] = list(v) if isinstance(v, tuple) else v
            elif not k.startswith("_"):
                public_dict[k] = list(v) if isinstance(v, tuple) else v
        if "enum" in public_dict and cls.__is__(public_dict["enum"]):
            public_dict["enum"] = cls.__get_value__(public_dict["enum"])
        return public_dict

    @classmethod
    def __value_repr__(cls, obj: Any) -> Any:
        if cls.__is__(obj):
            if cls.__has_value__(obj):
                val = cls.__get_value__(obj)
                return cls.__value_repr__(val)
            return {
                k: cls.__value_repr__(v)
                for k, v in vars(obj).items()
                if not k.startswith("_") and cls.__is__(v)
            }
        if isinstance(obj, (tuple, list)):
            return [cls.__value_repr__(v) for v in obj]
        return obj
