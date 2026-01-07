from functools import partial
from .client import DISCOSClient, DEFAULT_SUB_PORT, DEFAULT_REQ_PORT

SRTClient = partial(
    DISCOSClient,
    address="192.168.200.203",
    sub_port=DEFAULT_SUB_PORT,
    req_port=DEFAULT_REQ_PORT,
    telescope="SRT"
)
MedicinaClient = partial(
    DISCOSClient,
    address="192.168.1.100",
    sub_port=DEFAULT_SUB_PORT,
    req_port=DEFAULT_REQ_PORT,
    telescope="Medicina"
)
NotoClient = partial(
    DISCOSClient,
    address="192.167.187.17",
    sub_port=DEFAULT_SUB_PORT,
    req_port=DEFAULT_REQ_PORT,
    telescope="Noto"
)

del partial
del DEFAULT_SUB_PORT
del DEFAULT_REQ_PORT

__all__ = [
    "DISCOSClient",
    "SRTClient",
    "MedicinaClient",
    "NotoClient",
]
