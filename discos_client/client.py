from __future__ import annotations
import json
import weakref
from threading import Thread, Lock, Event
from collections import defaultdict
from typing import Any
from pathlib import Path
import zmq
from zmq.utils.monitor import recv_monitor_message
from .namespace import DISCOSNamespace
from .utils import rand_id, get_auth_keys, timestamp
from .initializer import NSInitializer


__all__ = ["DISCOSClient", "SRTClient", "MedicinaClient", "NotoClient"]

DEFAULT_SUB_PORT = 16000
DEFAULT_REQ_PORT = 16010


class DISCOSClient:
    """
    Class that implements a generic DISCOSClient. It handles incoming ZMQ
    messages from the DISCOS control software and eventually allows the user
    to send remote commands.
    """

    def __init__(
        self,
        *topics: str,
        address: str,
        sub_port: int = DEFAULT_SUB_PORT,
        req_port: int = DEFAULT_REQ_PORT,
        telescope: str | None = None,
        identity: str | None = None,
        server_public_key_file: str | Path | None = None,
    ) -> None:
        """
        :param topics: topic names to subscribe to.
        :param address: IP address to subscribe to.
        :param sub_port: TCP port where the subscriber socket will connect.
        :param req_port: TCP port where the requester socket will connect.
        :param telescope: name of the telescope the client is connecting to.
        :param identity: name of the key file to be used for sending remote
                         commands. Ideally, each application should have and
                         use its own identity.
        :param server_public_key_file: path to a ZMQ public certificate file
                                       containing the RPC server public key.
                                       Useful when using plain DISCOSClient
                                       without a predefined telescope profile.
        :raises ValueError: If one or more given topics are not known.
        :raises FileNotFoundError: If the provided identity file is missing.
        :raises ValueError: If the the provided identity file does not contain
                            a valid key pair.
        """
        if telescope not in ("Medicina", "Noto", "SRT", None):
            raise ValueError(f"Unknown telescope: '{telescope}'")
        self._initializer = NSInitializer(telescope)
        self._topics = self.__validate_topics__(self._initializer, topics)
        self._client_id = rand_id()
        self._stop = Event()
        self._context = zmq.Context()

        self._events = {}
        self._events["stop"] = self._stop

        self._sub = self._context.socket(zmq.SUB)
        self._sub.setsockopt(zmq.LINGER, 0)
        self._sub.setsockopt(zmq.RECONNECT_IVL, 1000)
        self._sub.setsockopt(zmq.CONNECT_TIMEOUT, 500)
        self._sub.connect(f"tcp://{address}:{sub_port}")

        self._sockets = {}
        self._sockets["sub"] = self._sub

        self._locks = defaultdict(Lock)

        self._receiver = Thread(
            target=self.__receive__,
            args=(
                self._sub,
                self._locks,
                self._client_id,
                self.__dict__,
                self._stop
            ),
            daemon=True
        )

        self._finalizer = weakref.finalize(
            self,
            self.__cleanup__,
            self._stop,
            self._receiver,
            self._sockets,
            self._context
        )

        if identity is not None:
            try:
                public, secret, server = get_auth_keys(
                    identity=identity,
                    telescope=telescope,
                    server_public_key_file=server_public_key_file,
                )
            except OSError as ex:
                raise ValueError(
                    f"Unknown or invalid identity '{identity}', "
                    "or invalid server public key."
                ) from ex
            self._client_public = public
            self._client_secret = secret
            self._server_public = server
            self.__init_req_socket__(f"tcp://{address}:{req_port}")
            self.command = self.__command__

        for topic in self._topics:
            self.__dict__[topic] = self._initializer.initialize(topic)

        self._receiver.start()
        for topic in self._topics:
            self._sub.subscribe(f"{self._client_id}{topic}")

    def __command__(self, cmd: str, *args) -> DISCOSNamespace:
        """
        Sends a command to the remote server.

        This method is only available if the DISCOSClient instance finds the
        correct authentication keys.

        :param cmd: The name of the command.
        :param args: A series of arguments to be inclueded in the command.
        :return: A DISCOSNamespace containing the command answer.
        """
        answer = self._initializer.initialize("command_answer", False)
        answer <<= {"command": cmd}
        if not self.__req_connected__():
            answer <<= self.__unreachable_error__()
            return answer

        payload = {"command": cmd, "async": True}
        if args:
            payload["args"] = args

        payload = json.dumps(payload, separators=(",", ":"))
        self._req.send_string(payload)

        while self.__req_connected__(strict=True):
            if (self._req.poll(10) & zmq.POLLIN) != 0:
                answer <<= json.loads(self._req.recv_string())
                return answer

        # We lost connection between send and receive, we need to reinitialize
        # the REQ socket
        endpoint = self._req.get_string(zmq.LAST_ENDPOINT)
        self._mon.close()
        self._req.close()
        self.__init_req_socket__(endpoint)
        answer <<= self.__unreachable_error__()
        return answer

    def __init_req_socket__(self, endpoint: str) -> None:
        self._req = self._context.socket(zmq.REQ)
        self._req.setsockopt(zmq.LINGER, 0)
        self._req.setsockopt(zmq.IMMEDIATE, 1)
        self._req.setsockopt(zmq.RECONNECT_IVL, 1000)
        self._req.setsockopt(zmq.CONNECT_TIMEOUT, 500)
        self._req.setsockopt(zmq.HEARTBEAT_IVL, 1000)
        self._req.setsockopt(zmq.HEARTBEAT_TIMEOUT, 1000)
        self._req.curve_publickey = self._client_public
        self._req.curve_secretkey = self._client_secret
        self._req.curve_serverkey = self._server_public
        self._mon = self._req.get_monitor_socket()
        self._online = Event()
        self._events["online"] = self._online
        self._req.connect(endpoint)
        self._sockets["req"] = self._req
        self._sockets["mon"] = self._mon

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
        receiver: Thread,
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
            receiver.join()
        except RuntimeError:  # pragma: no cover
            pass
        for _, socket in sockets.items():
            socket.disable_monitor()
            socket.close()
        context.term()

    @staticmethod
    def __receive__(
        sub: zmq.Socket,
        locks: dict[str, Lock],
        client_id: str,
        namespaces: dict[str, DISCOSNamespace],
        stop: Event
    ) -> None:
        """
        Loops continuously waiting for new ZMQ messages.

        :param socket: The ZMQ socket object.
        :param locks: The locks dictionary, used for thread synchronization.
        :param client_id: The random string identifying the client.
        :param d: The client __dict__ object.
        :param event: The Event object that will break the receiver loop.
        """
        while not stop.is_set():
            if (sub.poll(10) & zmq.POLLIN) != 0:
                t, p = sub.recv_multipart()  # noqa
                t = t.decode("ascii")
                if t.startswith(client_id):
                    sub.unsubscribe(t)
                    t = t[len(client_id):]
                    sub.subscribe(t)
                p = json.loads(p)
                with locks[t]:
                    namespaces[t] <<= p

    def __req_connected__(self, strict: bool = False) -> bool:
        """
        Checks if the REQ socket is connected.

        :param strict: If True, this method will return false if a
                       disconnection happened, even if the socket was
                       finally reconnected.
        :return: A boolean indicating where the REQ socket is connected.
        """
        disconnection_detected = False
        while self._mon.poll(0) & zmq.POLLIN:
            msg = recv_monitor_message(self._mon)
            event = msg["event"]
            if event == zmq.EVENT_CONNECTED:
                self._online.set()
            elif event in (zmq.EVENT_DISCONNECTED, zmq.EVENT_CLOSED):
                self._online.clear()
                disconnection_detected = True
        currently_online = self._online.is_set()
        if strict:
            return currently_online and not disconnection_detected
        return currently_online

    @staticmethod
    def __unreachable_error__() -> dict[str, Any]:
        """
        Returns a DISCOSUnreachableError answer.

        :return: The DISCOSUnreachable answer.
        """
        return {
            "executed": False,
            "error_trace": [{
                "message": "DISCOS is unreachable",
                "category": 2101,   # ClientErrors
                "code": 14,         # DISCOSUnreachableError
            }],
            "timestamp": timestamp()
        }

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

            | 't' - tight JSON
            | '<n>i' - indented JSON \
with optional indentation level <n> (default is 2)
            | 'e' - entire representation with metadata
            | 'm' - metadata only representation

        :return: A JSON formatted string.
        :raises ValueError: If the given format specifier is not known or
                            contains errors.
        """
        has_e = "e" in spec
        has_m = "m" in spec

        if has_e and has_m:
            raise ValueError(
                "Format specifier cannot contain both 'e' and 'm'."
            )

        if has_e:
            fmt_spec = spec[1:] if spec.startswith("e") else spec
            fmt_spec = fmt_spec[:-1] if fmt_spec.endswith("e") else fmt_spec
        elif has_m:
            fmt_spec = spec[1:] if spec.startswith("m") else spec
            fmt_spec = fmt_spec[:-1] if fmt_spec.endswith("m") else fmt_spec
        else:
            fmt_spec = spec

        indent = None
        separators = None
        default = (
            DISCOSNamespace.__full_dict__ if has_e
            else DISCOSNamespace.__metadata_dict__ if has_m
            else DISCOSNamespace.__message_dict__
        )

        if fmt_spec == "":
            pass
        elif fmt_spec == "t":
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


class SRTClient(DISCOSClient):
    # pylint: disable=too-few-public-methods
    """
    Creates a client configured for the **Sardinia Radio Telescope (SRT)**.
    """

    def __init__(self, *topics: str, identity: str | None = None) -> None:
        """
        :param topics: Topic names to subscribe to.
        :param identity: Name of the key pair file to be used in order to
                              send commands.
        """
        super().__init__(
            *topics,
            address="192.168.200.203",
            telescope="SRT",
            identity=identity
        )


class MedicinaClient(DISCOSClient):
    # pylint: disable=too-few-public-methods
    """
    Creates a client configured for the **Medicina Radio Telescope**.
    """

    def __init__(self, *topics: str, identity: str | None = None) -> None:
        """
        :param topics: Topic names to subscribe to.
        :param identity: Name of the key pair file to be used in order to
                              send commands.
        """
        super().__init__(
            *topics,
            address="192.168.1.100",
            telescope="Medicina",
            identity=identity
        )


class NotoClient(DISCOSClient):
    # pylint: disable=too-few-public-methods
    """
    Creates a client configured for the **Noto Radio Telescope**.
    """

    def __init__(self, *topics: str, identity: str | None = None) -> None:
        """
        :param topics: Topic names to subscribe to.
        :param identity: Name of the key pair file to be used in order to
                              send commands.
        """
        super().__init__(
            *topics,
            address="192.167.187.17",
            telescope="Noto",
            identity=identity
        )
