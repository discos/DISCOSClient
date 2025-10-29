from __future__ import annotations
import json
import threading
import weakref
from concurrent.futures import ProcessPoolExecutor, Future
from collections import defaultdict
from typing import Any, cast, Tuple, Dict
import zmq
from .namespace import DISCOSNamespace
from .utils import rand_id, SchemaMerger


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
        """
        self_ref = weakref.ref(self)
        self._client_id = rand_id()
        self._schema_merger = SchemaMerger(telescope)
        self._waiting = defaultdict(list)
        self._waiting_lock = threading.Lock()
        self._locks = defaultdict(threading.Lock)
        self._pool = ProcessPoolExecutor()
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.RCVTIMEO, 10)
        self._socket.connect(f'tcp://{address}:{port}')
        self._recv_thread = threading.Thread(
            target=self.__recv__,
            args=(self_ref,),
            daemon=True
        )
        self._finalizer = weakref.finalize(
            self,
            self.__cleanup__,
            self._pool,
            self._socket,
            self._context,
        )
        valid_topics = self._schema_merger.get_topics()
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
            topics = self._schema_merger.get_topics()
        self._topics = list(topics)
        for t in self._topics:
            self.__update_namespace__(t, DISCOSNamespace(
                **self._schema_merger.merge_schema(t, {})
            ))
            self._socket.subscribe(f'{self._client_id}{t}')
        self._recv_thread.start()

    @staticmethod
    def __cleanup__(
        pool: ProcessPoolExecutor,
        socket: zmq.socket,
        context: zmq.Context,
    ) -> None:
        """
        Joins the merge task pool, closes the ZMQ socket and context.

        :param pool: the ProcessPoolExecutor object to be shutdown.
        :param socket: the ZMQ socket to be closed.
        :param context: the ZMQ context to be closed.
        """
        socket.close()
        context.term()
        pool.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def __recv__(self_ref: weakref.ReferenceType["DISCOSClient"]) -> None:
        """
        Cycles infinitely waiting for new messages. When a new one is received,
        it submit a merge task to the ProcessPoolExecutor.

        :param self_ref: weak reference to the DISCOSClient instance.
        """
        while True:
            self = self_ref()
            if self is None:
                break
            self = cast("DISCOSClient", self)
            try:
                message = self._socket.recv_multipart()
                topic, payload = message[0].decode("ascii"), message[1]
                if topic.startswith(self._client_id):
                    self._socket.unsubscribe(topic)
                    topic = topic[len(self._client_id):]
                    self._socket.subscribe(topic)
                fut = self._pool.submit(
                    DISCOSClient.__merge_task__,
                    topic,
                    payload,
                    self._schema_merger
                )
                fut.add_done_callback(
                    lambda f, w=self_ref: DISCOSClient.__update_task__(w, f)
                )
            except zmq.Again:
                # No data received, cycle again
                pass
            except (zmq.ContextTerminated, zmq.ZMQError):  # pragma: no cover
                # Access to socket after it was closed
                break
            except RuntimeError:  # pragma: no cover
                # Submit after pool shutdown
                break
            finally:
                del self

    @staticmethod
    def __merge_task__(
        topic: str,
        payload: bytes,
        merger: SchemaMerger
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Performs the merging between payload and schema. This task can be very
        CPU expensive, therefore it is executed as a separate process.

        :param topic:
        :param payload:
        :param merger:
        """
        return topic, merger.merge_schema(topic, json.loads(payload))

    @staticmethod
    def __update_task__(
        self_ref: weakref.ReferenceType["DISCOSClient"],
        fut: Future
    ) -> None:
        """
        Updates the inner DISCOSNamespace cache and notifies the waiters.

        :param self_ref: weak reference to the DISCOSClient instance.
        :param fut: the Future object containing the results of the merge task.
        """
        self = self_ref()
        if self is None:
            return
        self = cast("DISCOSClient", self)
        try:
            topic, payload = fut.result()
            payload = DISCOSNamespace(**payload)
            with self._locks[topic]:
                self.__update_namespace__(topic, payload)
        finally:
            del self

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

    def __repr__(self) -> str:
        """
        Custom object representation method.

        :return: Unambiguous string representation.
        """
        return f"<{self.__class__.__name__}({self.__public_dict__()})>"

    def __str__(self) -> str:
        """
        Custom string representation method.

        :return: A JSON representation of the object, with indentation=2
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

        :return: A JSON formatted string.
        """
        fmt_spec = spec[1:] if spec.startswith("f") else spec
        fmt_spec = fmt_spec[:-1] if fmt_spec.endswith("f") else fmt_spec

        indent = None
        separators = None
        default = DISCOSNamespace.__full_dict__ if fmt_spec != spec \
            else DISCOSNamespace.__message_dict__

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
        return dict(filter(
            lambda item: item[0] in self._topics, self.__dict__.items()
        ))
