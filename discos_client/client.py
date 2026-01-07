from __future__ import annotations
import json
import weakref
from threading import Thread, Lock, Event
from collections import defaultdict
from typing import Any
import zmq
from zmq.utils.monitor import recv_monitor_message
from .namespace import DISCOSNamespace
from .utils import rand_id, get_auth_keys
from .initializer import NSInitializer


__all__ = [
    "DEFAULT_SUB_PORT",
    "DEFAULT_REQ_PORT",
    "DISCOSClient"
]

DEFAULT_SUB_PORT = 16000
DEFAULT_REQ_PORT = 16010


class DISCOSClient:
    """
    Class that implements a DISCOSClient. It handles incoming ZMQ messages from
    the DISCOS control software.
    """

    def __init__(
        self,
        *topics: str,
        address: str,
        sub_port: int,
        req_port: int | None = None,
        telescope: str | None = None
    ) -> None:
        """
        Initializes the class instance.

        :param topics: topic names to subscribe to.
        :param address: IP address to subscribe to.
        :param sub_port: TCP port where the subscriber socket will connect.
        :param req_port: TCP port where the requester socket will connect.
        :param telescope: name of the telescope the client is connecting to.
        :raises ValueError: If one or more given topics are not known.
        """
        if telescope not in ("Medicina", "Noto", "SRT", None):
            raise ValueError(f"Unknown telescope: '{telescope}'")
        initializer = NSInitializer(telescope)
        self._topics = self.__validate_topics__(initializer, topics)
        self._client_id = rand_id()
        self._stop = Event()
        self._context = zmq.Context()

        events = {}
        events["stop"] = self._stop

        self._sub = self._context.socket(zmq.SUB)
        self._sub.setsockopt(zmq.LINGER, 0)
        self._sub.setsockopt(zmq.RCVTIMEO, 10)
        self._sub.setsockopt(zmq.RECONNECT_IVL, 1000)
        self._sub.setsockopt(zmq.CONNECT_TIMEOUT, 500)
        self._sub.connect(f"tcp://{address}:{sub_port}")

        sockets = {}
        sockets["sub"] = self._sub

        if req_port and telescope:
            self.__init_req_socket__(
                address, req_port, telescope, events, sockets
            )

        self._locks = defaultdict(Lock)

        for topic in self._topics:
            self.__dict__[topic] = initializer.initialize(topic)

        self._updater = Thread(
            target=self.__update__,
            args=(
                self._client_id,
                sockets,
                self._locks,
                self.__dict__,
                events,
            ),
            daemon=True
        )

        self._finalizer = weakref.finalize(
            self,
            self.__cleanup__,
            self._stop,
            self._updater,
            sockets,
            self._context
        )

        self._updater.start()
        for topic in self._topics:
            self._sub.subscribe(f"{self._client_id}{topic}")

    def __init_req_socket__(
        self,
        address: str,
        req_port: int,
        telescope: str,
        events: dict[str, Event],
        sockets: dict[str, zmq.Socket]
    ) -> None:
        try:
            client_public, client_secret, server_public = get_auth_keys(
                telescope
            )
        except OSError:
            # A curve key is missing, this
            # telemetry and will not be able to send commands
            return
        self._req = self._context.socket(zmq.REQ)
        self._req.setsockopt(zmq.LINGER, 0)
        self._req.setsockopt(zmq.IMMEDIATE, 1)
        self._req.setsockopt(zmq.SNDTIMEO, 0)
        self._req.setsockopt(zmq.RECONNECT_IVL, 1000)
        self._req.setsockopt(zmq.CONNECT_TIMEOUT, 500)
        self._req.setsockopt(zmq.HEARTBEAT_IVL, 1000)
        self._req.setsockopt(zmq.HEARTBEAT_TIMEOUT, 1000)
        self._req.curve_publickey = client_public
        self._req.curve_secretkey = client_secret
        self._req.curve_serverkey = server_public
        self._mon = self._req.get_monitor_socket()
        self._online = Event()
        events["online"] = self._online
        self._req.connect(f"tcp://{address}:{req_port}")
        sockets["req"] = self._req
        sockets["mon"] = self._mon
        self.command = self.__command__

    @staticmethod
    def __validate_topics__(
        initializer: NSInitializer,
        topics: tuple[str]
    ) -> list[str]:
        valid_topics = initializer.get_topics()
        invalid = [t for t in topics if t not in valid_topics]
        if not invalid:
            return topics or valid_topics

        if len(invalid) > 1:
            invalid = f"""s '{"', '".join(invalid[:-1])}'""" \
                      f" and '{invalid[-1]}' are"
        else:
            invalid = f""" '{invalid[0]}' is"""

        raise ValueError(
            f"Topic{invalid} not known, choose among "
            f"""'{"', '".join(valid_topics[:-1])} and """
            f"'{valid_topics[-1]}'"
        )

    @staticmethod
    def __cleanup__(
        stop: Event,
        updater: Thread,
        sockets: dict[str, zmq.Socket],
        context: zmq.Context
    ) -> None:
        """
        Joins the updater thread and closes the ZMQ sockets and context.

        :param stop: the Event object that will stop the updater thread.
        :param sub: the ZMQ SUB socket object.
        :param context: the ZMQ context object.
        :param updater: the updater thread object.
        """
        stop.set()
        try:
            updater.join()
        except RuntimeError:  # pragma: no cover
            pass
        for _, socket in sockets.items():
            socket.disable_monitor()
            socket.close()
        context.term()

    @staticmethod
    def __update__(
        client_id: str,
        sockets: dict[str, zmq.Socket],
        locks: dict[str, Lock],
        namespaces: dict[str, DISCOSNamespace],
        events: dict[str, Event]
    ) -> None:
        """
        Loops continuously waiting for new ZMQ messages and events.

        :param client_id: The random string identifying the client.
        :param sockets: The dictionary containing the ZMQ sockets.
        :param locks: The locks dictionary, used for thread synchronization.
        :param namespaces: The client __dict__ object, containing the
                           DISCOSNamespaces.
        :param events: The dictionary containing the Event objects for
                       synchronization.
        """
        sub = sockets.get("sub")
        mon = sockets.get("mon")
        stop = events.get("stop")
        online = events.get("online")

        poller = zmq.Poller()
        poller.register(sub, zmq.POLLIN)
        if mon is not None:
            poller.register(mon, zmq.POLLIN)
        while not stop.is_set():
            zmq_events = {}
            try:
                zmq_events = dict(poller.poll(timeout=200))
            except zmq.ZMQError:  # pragma: no cover
                break

            if sub in zmq_events:
                try:
                    t, p = sub.recv_multipart(flags=zmq.DONTWAIT)  # noqa
                    t = t.decode("ascii")
                    if t.startswith(client_id):
                        sub.unsubscribe(t)
                        t = t[len(client_id):]
                        sub.subscribe(t)
                    p = json.loads(p)
                    with locks[t]:
                        namespaces[t] <<= p
                except zmq.Again:  # pragma: no cover
                    # We should never get here since there will always be
                    # some data to recover from the socket
                    pass

            if mon is not None and mon in zmq_events:
                while True:
                    try:
                        event = recv_monitor_message(mon, flags=zmq.DONTWAIT)
                    except zmq.Again:
                        break

                    event = event["event"]
                    if event == zmq.EVENT_CONNECTED:
                        online.set()
                    elif event in \
                            (zmq.EVENT_DISCONNECTED, zmq.EVENT_CLOSED):
                        online.clear()

    def __command__(self, cmd: str, *args) -> dict[str, Any]:
        if self._online.is_set():
            message = {"command": cmd}
            if args:
                message["args"] = args
            payload = json.dumps(message, separators=(",", ":"))
            self._req.send_string(payload)
            answer = json.loads(self._req.recv_string())
        else:
            answer = {
                "executed": False,
                "error": {
                    "type": 2101,  # ClientErrors
                    "code": 14,    # DISCOSUnreachableError
                    "description": "DISCOS is unreachable"
                }
            }
        return answer

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
