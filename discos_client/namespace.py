from __future__ import annotations
import json
import threading
from copy import deepcopy
from typing import Any, Callable, Iterator
from .utils import delegated_operations, delegated_comparisons, public_dict


__all__ = ["DISCOSNamespace"]


@delegated_operations('__value_operation__')
@delegated_comparisons('__value_comparison__')
class DISCOSNamespace:
    """
    Immutable recursive container for structured data.

    This class wraps nested dictionaries and lists into nested
    DISCOSNamespace instances and allows limited operations on
    primitive values. All attributes are read-only.
    """

    __typename__ = "DISCOSNamespace"
    __private__ = (
        "type",
        "title",
        "description",
        "enum",
        "unit",
        "format",
        "_observers",
        "_observers_lock",
        "bind",
        "unbind",
        "wait",
        "copy"
    )

    def __init__(self, **kwargs: Any) -> None:
        """
        Construct a DISCOSNamespace object, recursively wrapping
        dictionaries and lists as DISCOSNamespace instances.

        Special keys "items" and "value" are stored as internal
        value containers.

        :param kwargs: Arbitrary keyword arguments to initialize attributes.
        """
        object.__setattr__(self, "_observers", set())
        object.__setattr__(self, "_observers_lock", threading.Lock())

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
                k = "_value"
            kwargs[k] = transform(v)
        self.__dict__.update(kwargs)

    def bind(self, callback: Callable[[DISCOSNamespace], None]) -> None:
        """
        Bind a callback to the DISCOSNamespace object,
        to be notified when it changes.

        :param callback: A function that receives the updated object
                         when obj changes.
        """
        with self._observers_lock:
            self._observers.add(callback)

    def unbind(self, callback: Callable[[DISCOSNamespace], None]) -> None:
        """
        Unbind a previously registered callback from the DISCOSNamespace
        object.

        :param callback: The callback function to remove.
        """
        with self._observers_lock:
            self._observers.discard(callback)

    def wait(self, timeout: float = None) -> DISCOSNamespace:
        """
        Block until the DISCOSNamespace triggers a change notification.

        :param timeout: Optional timeout in seconds.
        :return: The updated object, or None if the timeout occurred.
        """
        event = threading.Event()

        def callback(_):
            event.set()

        self.bind(callback)
        try:
            event.wait(timeout)
        finally:
            self.unbind(callback)
        return self

    def copy(self) -> DISCOSNamespace:
        """
        Return a copy of the DISCOSNamespace.
        """
        return deepcopy(self)

    def __value_operation__(self, operation: Callable[[Any], Any]) -> Any:
        """
        Apply an operation to the internal value if it is primitive.

        :param operation: A function to apply.
        :return: Result of applying the operation to the internal value.
        :raises TypeError: If the object does not hold a primitive value.
        """
        if self.__has_value__(self) and \
                not DISCOSNamespace.__is__(self._value):
            return operation(self._value)
        raise TypeError(
            f"{self.__typename__} supports operations "
            "only when holding a primitive value"
        )

    def __value_comparison__(
        self,
        op: Callable[[Any, Any], bool],
        other: Any
    ) -> bool:
        """
        Apply a comparison to the internal value if it is primitive,
        or to the inner __dict__ if both operands are DISCOSNamespace
        """
        if DISCOSNamespace.__is__(other):
            try:
                return op(
                    {
                        k: v
                        for k, v in vars(self).items()
                        if not k.startswith("_") or k == "_value"
                    },
                    {
                        k: v
                        for k, v in vars(other).items()
                        if not k.startswith("_") or k == "_value"
                    },
                )
            except TypeError:
                return False
        if DISCOSNamespace.__has_value__(self):
            return op(self._value, other)

        return False

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        if self.__has_value__(self):
            return repr(self._value)
        return f"<{self.__typename__}({self.__value_repr__(self)})>"

    def __str__(self) -> str:
        """Return a string representation of the object."""
        if self.__has_value__(self):
            return str(self._value)
        return format(self, "")

    def __int__(self) -> int:
        """Return the internal value as an integer."""
        if self.__has_value__(self):
            return int(self._value)
        raise TypeError(
            f"{self.__typename__} object cannot be converted to int"
        )

    def __float__(self) -> float:
        """Return the internal value as a float."""
        if self.__has_value__(self):
            return float(self._value)
        raise TypeError(
            f"{self.__typename__} object cannot be converted to float"
        )

    def __neg__(self) -> Any:
        """Return the negated internal value."""
        if self.__has_value__(self):
            return -self._value
        raise TypeError(
            f"{self.__typename__} object cannot be negated"
        )

    def __bool__(self) -> bool:
        """Return the boolean representation of the internal value."""
        if self.__has_value__(self):
            return bool(self._value)
        raise TypeError(
            f"{self.__typename__} object cannot be converted to bool"
        )

    def __getitem__(self, item: Any) -> Any:
        """
        Support indexing if the object holds a subscriptable value.

        :param item: Index or key.
        :return: Corresponding element.
        :raises TypeError: If not subscriptable.
        """
        if self.__has_value__(self):
            return self._value[item]
        raise TypeError(f"{self.__typename__} object is not subscriptable")

    def __len__(self) -> int:
        """Return the length of the internal value if applicable."""
        if self.__has_value__(self):
            return len(self._value)
        raise TypeError(f"{self.__typename__} object has no length")

    def __iter__(self) -> Iterator[Any]:
        """Return an iterator over the internal value if iterable."""
        if self.__has_value__(self):
            return iter(self._value)
        raise TypeError(f"{self.__typename__} object is not iterable")

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent attribute assignment."""
        raise TypeError(
            f"{self.__typename__} is read-only and "
            "does not allow attribute assignment"
        )

    def __delattr__(self, name: str) -> None:
        """Prevent attribute deletion."""
        raise TypeError(
            f"{self.__typename__} is read-only and "
            "does not allow attribute deletion"
        )

    def __ilshift__(self, other: DISCOSNamespace) -> DISCOSNamespace:
        """
        In-place merge of another DISCOSNamespace.

        :param other: Another DISCOSNamespace or compatible object.
        :return: Self after the merge.
        """
        if self == other:
            return self

        for k, ov in vars(other).items():
            if k.startswith("_") and k != "_value":
                continue

            sv = getattr(self, k, None)

            if DISCOSNamespace.__is__(sv) and DISCOSNamespace.__is__(ov):
                sv <<= ov
            else:
                if ov == sv:
                    continue
                new = deepcopy(ov)
                object.__setattr__(self, k, new)

        self.__notify__()
        return self

    def __format__(self, spec: str) -> str:
        """
        Custom format method.

        :param spec: Format specifier.

            | 'c' - compact JSON
            | '<n>i' - indented JSON \
with optional indentation level <n> (default is 2)
            | 'f' - full representation with metadata

        :return: A JSON formatted string.
        """
        if self.__has_value__(self):
            return format(self._value, spec)

        fmt_spec = spec[1:] if spec.startswith("f") else spec
        fmt_spec = fmt_spec[:-1] if fmt_spec.endswith("f") else fmt_spec

        indent = None
        separators = None
        default = \
            self.__full_dict__ if fmt_spec != spec else self.__message_dict__

        if fmt_spec == "":
            pass
        elif fmt_spec == "c":
            separators = (",", ":")
        elif fmt_spec.endswith("i"):
            fmt_par = fmt_spec[:-1]
            indent = 2
            if fmt_par:
                try:
                    indent = int(fmt_par)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid indent in format spec: '{fmt_spec[:-1]}'"
                    ) from exc
                if indent <= 0:
                    raise ValueError("Indentation must be a positive integer")
        else:
            raise ValueError(
                f"Unknown format code '{spec}' for {self.__typename__}"
            )

        return json.dumps(
            self,
            default=default,
            indent=indent,
            separators=separators,
            sort_keys=True,
            ensure_ascii=False
        )

    def __deepcopy__(self, memo):
        """
        Return a deep copy of the object.

        :param memo: Internal memoization dictionary for deepcopy.
        :return: A new deepcopy of this object.
        """
        cls = self.__class__
        public = cls.__full_dict__(self)
        copied = deepcopy(public, memo)
        return cls(**copied)

    @classmethod
    def __get_value__(cls, obj: DISCOSNamespace) -> Any:
        """
        Get the internal stored value of a DISCOSNamespace instance.

        :param obj: The object to retrieve the value from.
        :return: The stored value (list if originally a tuple).
        """
        value = object.__getattribute__(obj, "_value")
        if isinstance(value, tuple):
            value = list(value)
        return value

    @classmethod
    def __has_value__(cls, obj: Any) -> bool:
        """
        Check if an object has a stored value.

        :param obj: The object to check.
        :return: True if it has a value, False otherwise.
        """
        return hasattr(obj, "_value")

    @classmethod
    def __is__(cls, obj: Any) -> bool:
        """
        Check if an object is an instance of DISCOSNamespace.

        :param obj: The object to check.
        :return: True if instance, False otherwise.
        """
        return isinstance(obj, cls)

    @classmethod
    def __full_dict__(cls, obj: DISCOSNamespace) -> dict[str, Any]:
        """
        Return a dictionary representation for JSON serialization.

        :param obj: The object to convert.
        :return: A dictionary with public fields and metadata.
        """
        return public_dict(
            obj,
            cls.__is__,
            cls.__get_value__
        )

    @classmethod
    def __message_dict__(cls, obj: DISCOSNamespace) -> dict[str, Any]:
        """
        Return the pure message (value-only) dictionary,
        removing schema metadata.

        :param obj: The object to convert.
        :return: A dictionary with public fields.
        """
        def unwrap(value: Any) -> Any:
            if cls.__is__(value):
                if cls.__has_value__(value):
                    return unwrap(cls.__get_value__(value))
                retval = {}
                for k, v in vars(value).items():
                    if k in cls.__private__:
                        continue
                    retval[k] = unwrap(v)
                return retval
            if isinstance(value, (list, tuple)):
                return [unwrap(v) for v in value]
            return value
        return unwrap(obj)

    @classmethod
    def __value_repr__(cls, obj: Any) -> Any:
        """
        Recursively return a clean representation of the value.

        :param obj: The object to represent.
        :return: A simplified structure with primitive values and lists.
        """
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

    def __notify__(self) -> None:
        """
        Execute the bound callbacks, if are present
        """
        with self._observers_lock:
            for cb in self._observers:
                cb(self)
