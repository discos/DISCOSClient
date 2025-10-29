from functools import partial
from .client import DISCOSClient

DEFAULT_PORT = 16000

SRTClient = partial(
    DISCOSClient,
    address="192.168.200.203",
    port=DEFAULT_PORT,
    telescope="SRT"
)
MedicinaClient = partial(
    DISCOSClient,
    address="192.168.1.100",
    port=DEFAULT_PORT,
    telescope="Medicina"
)
NotoClient = partial(
    DISCOSClient,
    address="192.167.187.17",
    port=DEFAULT_PORT,
    telescope="Noto"
)

del partial
del DEFAULT_PORT

__all__ = [
    "DISCOSClient",
    "SRTClient",
    "MedicinaClient",
    "NotoClient",
]
