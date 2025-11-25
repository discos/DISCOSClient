from __future__ import annotations
import json
import weakref
from threading import Thread, Lock, Event
from collections import defaultdict
import zmq
from .namespace import DISCOSNamespace
from .utils import rand_id
from .initializer import NSInitializer


__all__ = [
    "DEFAULT_PORT",
    "DISCOSClient"
]

DEFAULT_PORT = 16000


class DISCOSClient:
    """
    Class that implements a DISCOSClient. It handles incoming ZMQ messages from
    the DISCOS control software.
    """

    def __init__(
        self,
        *topics: str,
        address: str,
        port: int,
        telescope: str | None = None
    ) -> None:
        """
        Initializes the class instance.

        :param topics: topic names to subscribe to.
        :param address: IP address to subscribe to.
        :param port: TCP port to subscribe to.
        :param telescope: name of the telescope the client is connecting to.
        :raises ValueError: If one or more given topics are not known.
        """
        initializer = NSInitializer(telescope)
        valid_topics = initializer.get_topics()
        invalid = [t for t in topics if t not in valid_topics]
        if invalid:
            if len(invalid) > 1:
                invalid = \
                    f"""s '{"', '".join(invalid[:-1])}'""" \
                    f" and '{invalid[-1]}' are"
            else:
                invalid = f""" '{invalid[0]}' is"""
            raise ValueError(
                f"Topic{invalid} not known, choose among "
                f"""'{"', '".join(valid_topics[:-1])} and """
                f"'{valid_topics[-1]}'"
            )
        if not topics:
            topics = initializer.get_topics()
        self._topics = topics
        self._client_id = rand_id()
        self._event = Event()
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.RCVTIMEO, 10)
        self._socket.connect(f"tcp://{address}:{port}")

        self._locks = defaultdict(Lock)

        for topic in self._topics:
            self.__dict__[topic] = initializer.initialize(topic)

        self._receiver = Thread(
            target=self.__receive__,
            args=(
                self._socket,
                self._locks,
                self._client_id,
                self.__dict__,
                self._event
            ),
            daemon=True
        )

        self._finalizer = weakref.finalize(
            self,
            self.__cleanup__,
            self._event,
            self._socket,
            self._context,
            self._receiver
        )

        self._receiver.start()
        for topic in self._topics:
            self._socket.subscribe(f"{self._client_id}{topic}")

    @staticmethod
    def __cleanup__(
        event: Event,
        socket: zmq.Socket,
        context: zmq.Context,
        receiver: Thread
    ) -> None:
        """
        Joins the receiver thread and closes the ZMQ socket and context.

        :param event: the Event object that will stop the receiver thread.
        :param socket: the ZMQ socket object.
        :param context: the ZMQ context object.
        :param receiver: the receiver thread object.
        """
        event.set()
        receiver.join()
        socket.close()
        context.term()

    @staticmethod
    def __receive__(
        socket: zmq.Socket,
        locks: dict[str, Lock],
        client_id: str,
        d: dict[str, DISCOSNamespace],
        event: Event
    ) -> None:
        """
        Loops continuously waiting for new ZMQ messages.

        :param socket: The ZMQ socket object.
        :param locks: The locks dictionary, used for thread synchronization.
        :param client_id: The random string identifying the client.
        :param d: The client __dict__ object.
        :param event: The Event object that will break the receiver loop.
        """
        while not event.is_set():
            try:
                t, p = socket.recv_multipart()  # noqa
                t = t.decode("ascii")
                if t.startswith(client_id):
                    socket.unsubscribe(t)
                    t = t[len(client_id):]
                    socket.subscribe(t)
                p = json.loads(p)
                with locks[t]:
                    d[t] <<= p
            except zmq.Again:
                # No data received, cycle again
                pass

    def __repr__(self) -> str:
        """
        Custom object representation method.

        :return: Unambiguous string representation.
        """
        return f"<{self.__class__.__name__}({self.__public_dict__()})>"

    def __str__(self) -> str:
        """
        Custom string representation method.

        :return: A JSON representation of the object.
        """
        return format(self, "")

    def __format__(self, spec: str) -> str:
        """
        Custom format method.

        :param spec: Format specifier.

            | 'c' - compact JSON
            | '<n>i' - indented JSON \
with optional indentation level <n> (default is 2)
            | 'f' - full representation with metadata
            | 'm' - metadata only representation

        :return: A JSON formatted string.
        :raises ValueError: If the given format specifier is not known or
                            contains errors.
        """
        has_f = "f" in spec
        has_m = "m" in spec

        if has_f and has_m:
            raise ValueError(
                "Format specifier cannot contain both 'f' and 'm'."
            )

        if has_f:
            fmt_spec = spec[1:] if spec.startswith("f") else spec
            fmt_spec = fmt_spec[:-1] if fmt_spec.endswith("f") else fmt_spec
        elif has_m:
            fmt_spec = spec[1:] if spec.startswith("m") else spec
            fmt_spec = fmt_spec[:-1] if fmt_spec.endswith("m") else fmt_spec
        else:
            fmt_spec = spec

        indent = None
        separators = None
        default = (
            DISCOSNamespace.__full_dict__ if has_f
            else DISCOSNamespace.__metadata_dict__ if has_m
            else DISCOSNamespace.__message_dict__
        )

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
                f"Unknown format code '{spec}' for {self.__class__.__name__}"
            )

        return json.dumps(
            self.__public_dict__(),
            default=default,
            indent=indent,
            separators=separators,
            sort_keys=True,
            ensure_ascii=False
        )

    def __public_dict__(self) -> dict[str, DISCOSNamespace]:
        """
        Returns a dictionary containing the pairs of topics and
        DISCOSNamespaces, each one holding the latest status.

        :return: A dictionary containing the pairs of topics and
                 DISCOSNamespaces with last received statuses
        """
        result: dict[str, DISCOSNamespace] = {}
        for topic in self._topics:
            self._locks[topic].acquire()
        for topic in self._topics:
            ns = self.__dict__.get(topic)
            result[topic] = ns
        for topic in self._topics:
            self._locks[topic].release()
        return result
