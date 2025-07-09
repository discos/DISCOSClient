from functools import partial
from .client import DISCOSClient

DEFAULT_PORT = 16000

SRTClient = partial(
    DISCOSClient,
    address="127.0.0.1",
    port=DEFAULT_PORT,
    telescope="SRT"
)
MedicinaClient = partial(
    DISCOSClient,
    address="127.0.0.1",
    port=DEFAULT_PORT,
    telescope="Medicina"
)
NotoClient = partial(
    DISCOSClient,
    address="127.0.0.1",
    port=DEFAULT_PORT,
    telescope="Noto"
)

del partial
del DISCOSClient
del DEFAULT_PORT

__all__ = ["SRTClient", "MedicinaClient", "NotoClient"]
