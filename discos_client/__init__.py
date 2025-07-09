from functools import partial
from .client import DISCOSClient

SRTClient = partial(
    DISCOSClient,
    address="127.0.0.1",
    telescope="SRT"
)
MedicinaClient = partial(
    DISCOSClient,
    address="127.0.0.1",
    telescope="Medicina"
)
NotoClient = partial(
    DISCOSClient,
    address="127.0.0.1",
    telescope="Noto"
)

__all__ = ["SRTClient", "MedicinaClient", "NotoClient"]
