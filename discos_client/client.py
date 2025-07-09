from __future__ import annotations
import json
import threading
import asyncio
from random import SystemRandom
from collections import defaultdict
from copy import deepcopy
from typing import Any
import zmq
from .namespace import DISCOSNamespace
from .utils import load_schemas, merge_schema


class DISCOSClient:  # noqa
    """
    Factory class that returns a DISCOS client instance.

    Use this to create a DISCOSClient either in synchronous or
    asynchronous mode.
    """

    def __new__(
        cls,
        *topics: str,
        address: str,
        port: int,
        telescope: str | None = None,
        asynchronous: bool = False,
    ) -> SyncClient | AsyncClient:
        """
        Create an instance of SyncClient or AsyncClient, depending
        on the given arguments.

        :param topics: The topic names to subscribe to.
        :param address: The IP address to subscribe to.
        :param port: The TCP port to subscribe to.
        :param telescope: name of the telescope the client is connecting to.
        :param asyncronous: If True, returns an
                            :class:`~discos_client.client.AsyncClient`
                            otherwise, a
                            :class:`~discos_client.client.SyncClient`
        :return: An instance of :class:`~discos_client.client.SyncClient` or
                :class:`~discos_client.client.AsyncClient`
        :rtype: :class:`~discos_client.client.SyncClient` |
                :class:`~discos_client.client.AsyncClient`
        """
        client_class = AsyncClient if asynchronous else SyncClient
        return client_class(
            *topics,
            address=address,
            port=port,
            telescope=telescope
        )


class BaseClient:
    """
    Class that implements a base DISCOSClient class for SyncClient and
    AsyncClient.

    It contains the core attributes, methods and inner logic for the clients
    to work properly.
    """

    __typename__ = "DISCOSClient"

    def __init__(
        self,
        *topics: str,
        address: str,
        port: int,
        telescope: str | None = None,
    ) -> None:
        """
        Initializes the class instance. Loads the JSON schemas and opens the
        ZMQ socket connection.

        :param topics: topic names to subscribe to.
        :param address: IP address to subscribe to.
        :param port: TCP port to subscribe to.
        :param telescope: name of the telescope the client is connecting to.
        """
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.connect(f'tcp://{address}:{port}')
        self._telescope = telescope
        self._schemas = load_schemas(self._telescope)
        valid_topics = list(self._schemas.keys())

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
            topics = self._schemas.keys()
        self._topics = list(topics)
        self._waiting = defaultdict(list)
        self.__initialize__()

    def __del__(self):
        """
        Closes the ZMQ socket and context.
        """
        self._socket.close()
        self._context.term()

    def __initialize__(self) -> None:
        """
        Initializes the client inner DISCOSNamespaces by retrieving initial
        messages.
        """
        rand_id = str(SystemRandom().randint(0, 100)).zfill(3)
        self._socket.setsockopt(zmq.RCVTIMEO, 10)
        for t in self._topics:
            self._socket.subscribe(f'{rand_id}_{t}')
            try:
                message = self._socket.recv_string()
                topic, payload = self.__to_namespace__(
                    message,
                    self._schemas,
                    rand_id
                )
                self.__update_namespace__(topic, payload)
            except zmq.Again:  # pragma: no cover
                dummy = merge_schema(self._schemas[t], {})
                self.__update_namespace__(t, DISCOSNamespace(**dummy))
            self._socket.unsubscribe(f'{rand_id}_{t}')
        self._socket.setsockopt(zmq.RCVTIMEO, -1)
        for topic in self._topics:
            self._socket.subscribe(topic)

    def __update_namespace__(
        self,
        topic: str,
        payload: DISCOSNamespace
    ) -> None:
        """
        Updates or sets the given DISCOSNamespace for a given topic.

        :param topic: The topic relative to the given DISCOSNamespace object.
        :param payload: The new DISCOSNamespace object, used to update
                        the current one if already present in self.__dict__.
        """
        if topic in self.__dict__:
            self.__dict__[topic] <<= payload
        else:
            self.__dict__[topic] = payload

    @staticmethod
    def __to_namespace__(
        message: str,
        schemas: dict,
        rand_id: str = None
    ) -> DISCOSNamespace:
        """
        Merges a schema and a message into a DISCOSNamespace.

        :param message: The received JSON message, containing key-value pairs.
        :param schemas: The schemas dictionary.
        :param rand_id: Random identifier. Used to remove the said ID from the
                        topic name.
        :return: The merged DISCOSNamespace object.
        """
        topic, _, payload = message.partition(' ')
        if rand_id:
            topic = topic.replace(f"{rand_id}_", "")
        payload = merge_schema(
            schemas[topic],
            json.loads(payload)
        )
        return topic, DISCOSNamespace(**payload)

    def __repr__(self) -> str:
        """
        Custom object representation method.

        :return: Unambiguous string representation.
        """
        return f"<{self.__typename__}({self.__public_dict__()})>"

    def __str__(self) -> str:
        """
        Custom string representation method.

        :return: A JSON representation of the object, with indentation=2
        """
        return format(self, "2i")

    def __format__(self, spec: str) -> str:
        """
        Custom format method.

        :param spec: Format specifier. 'c' – compact JSON, \
'i' or '<n>i' – indented JSON, \
with optional indentation level <n> (default is 2)

        :return: A JSON formatted string.
        """
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
            self.__public_dict__(),
            default=DISCOSNamespace.__public_dict__,
            indent=indent,
            separators=separators
        )

    def __public_dict__(self) -> dict[str, DISCOSNamespace]:
        """
        Returns a dictionary containing the pairs of topics and
        DISCOSNamespaces, each one holding the latest status.

        :return: A dictionary containing the pairs of topics and
                 DISCOSNamespaces with last received statuses
        """
        return dict(filter(
            lambda item: item[0] in self._topics, self.__dict__.items()
        ))

    @staticmethod
    def __enumerate_paths__(topic, payload):
        """
        Yields all nested paths inside a DISCOSNamespace
        """
        yield topic
        for k, v in vars(payload).items():
            if not DISCOSNamespace.__is__(v) or "enum" in k:
                continue
            full_path = f"{topic}.{k}" if topic else k
            yield full_path
            if isinstance(v, DISCOSNamespace):
                yield from BaseClient.__enumerate_paths__(full_path, v)


class SyncClient(BaseClient):
    """
    Class that implements a synchronous DISCOSClient class.

    It contains the attributes necessary for the client to work in a threaded
    and synchronous environment.
    """

    def __init__(
        self,
        *topics: str,
        address: str,
        port: int,
        telescope: str | None,
    ) -> None:
        """
        Initializes the DISCOSClient base and SyncClient object,
        along with its attributes. Starts the message receiving thread
        in background.

        :param topics: The topic names to subscribe to.
        :param address: The IP address to subscribe to.
        :param port: The TCP port to subscribe to.
        :param telescope: name of the telescope the client is connecting to.
        """
        super().__init__(
            *topics,
            address=address,
            port=port,
            telescope=telescope
        )
        self.__waiting_lock = threading.Lock()
        self.__locks = defaultdict(threading.Lock)
        self.__update_thread = threading.Thread(
            target=self.__update__,
            daemon=True
        )
        self.__update_thread.start()

    def __update__(self) -> None:
        """
        Cycles infinitely waiting for new messages. When a new one is received,
        it updates the inner cache and notifies the waiters.
        """
        while True:
            message = self._socket.recv_string()
            topic, payload = self.__to_namespace__(message, self._schemas)
            with self.__locks[topic]:
                self.__update_namespace__(topic, payload)

            changed_paths = set(self.__enumerate_paths__(topic, payload))

            with self.__waiting_lock:
                to_remove = []
                for path, waiters in self._waiting.items():
                    if path in changed_paths:
                        for event, result in waiters:
                            result["value"] = self.__resolve_path__(path)
                            event.set()
                        to_remove.append(path)
                for path in to_remove:
                    del self._waiting[path]

    def __resolve_path__(self, path: str) -> Any:
        """
        Resolves the given path into the final attribute.

        :param path: the path the user is asking the namespace or value for.
        :return: the current DISCOSNamespace or value.
        """
        base_topic, *subpath = path.split(".")
        with self.__locks[base_topic]:
            obj = self.__dict__[base_topic]
            for key in subpath:
                obj = getattr(obj, key)
            return deepcopy(obj)

    def get(self, path: str, wait: bool = False) -> Any:
        """
        Retrieves the DISCOSNamespace for the given topic.

        :param path: the path the user is asking the namespace or value for.
        :param wait: a boolean indicating whether to wait for a new message
                     before returning the relative DISCOSNamespace or value.
        :return: the current or next received DISCOSNamespace or value.
        """
        base_topic = path.split(".")[0]
        if base_topic not in self._schemas:
            raise KeyError(f"Unknown topic '{base_topic}'")
        if base_topic not in self._topics:
            raise KeyError(f"The client is not subscribed to '{base_topic}'")
        if wait:
            event = threading.Event()
            result = {}
            with self.__waiting_lock:
                self._waiting.setdefault(path, []).append((event, result))
            event.wait()
            return deepcopy(result["value"])
        return deepcopy(self.__resolve_path__(path))


class AsyncClient(BaseClient):
    """
    Class that implements a asynchronous DISCOSClient class.

    It contains the attributes necessary for the client to work with asyncio.
    """

    def __init__(
        self,
        *topics: str,
        address: str,
        port: int,
        telescope: str | None,
    ) -> None:
        """
        Initialize the DISCOSClient base and AsyncClient object,
        along with its attributes. Starts the message receiving coroutine
        in the asyncio loop.

        :param topics: The topic names to subscribe to.
        :param address: The IP address to subscribe to.
        :param port: The TCP port to subscribe to.
        :param telescope: name of the telescope the client is connecting to.
        """
        super().__init__(
            *topics,
            address=address,
            port=port,
            telescope=telescope
        )
        self.__waiting_lock = asyncio.Lock()
        self.__locks = defaultdict(asyncio.Lock)
        self.__loop = asyncio.get_running_loop()
        self.__loop.create_task(self.__update__())

    async def __update__(self) -> None:
        """
        Cycles infinitely waiting for new messages. When a new one is received,
        it updates the inner cache and notifies the waiters.
        """
        try:
            while True:
                message = await self.__loop.run_in_executor(
                    None,
                    self._socket.recv_string
                )
                topic, payload = self.__to_namespace__(message, self._schemas)
                async with self.__locks[topic]:
                    self.__update_namespace__(topic, payload)

                changed_paths = set(
                    self.__enumerate_paths__(topic, payload)
                )

                async with self.__waiting_lock:
                    to_remove = []
                    for path, waiters in self._waiting.items():
                        if path in changed_paths:
                            for event, result in waiters:
                                result["value"] = await self.__resolve_path__(
                                    path
                                )
                                event.set()
                            to_remove.append(path)
                    for path in to_remove:
                        del self._waiting[path]
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    async def __resolve_path__(self, path: str) -> Any:
        """
        Resolves the given path into the final attribute.

        :param path: the path the user is asking the namespace or value for.
        :return: the current DISCOSNamespace or value.
        """
        base_topic, *subpath = path.split(".")
        async with self.__locks[base_topic]:
            obj = self.__dict__[base_topic]
            for key in subpath:
                obj = getattr(obj, key)
            return deepcopy(obj)

    async def get(self, path: str, wait: bool = False) -> DISCOSNamespace:
        """
        Retrieves the DISCOSNamespace for the given topic.

        :param path: the topic the user is asking the DISCOSNamespace for.
        :param wait: a boolean indicating whether to wait for a new message
                     before returning the relative DISCOSNamespace.
        :return: the current or next received DISCOSNamespace.
        """
        base_topic = path.split(".")[0]
        if base_topic not in self._schemas:
            raise KeyError(f"Unknown topic '{base_topic}'")
        if base_topic not in self._topics:
            raise KeyError(f"The client is not subscribed to '{base_topic}'")

        if wait:
            event = asyncio.Event()
            result = {}
            async with self.__waiting_lock:
                self._waiting.setdefault(path, []).append((event, result))
            await event.wait()
            return deepcopy(result["value"])
        return await self.__resolve_path__(path)
