#!/usr/bin/env python
import asyncio
from discos_client import DISCOSClient

async def main():
    SRT = DISCOSClient(address='127.0.0.1', asynchronous=True)
    while True:
        antenna = await SRT.get("antenna", wait=True)
        print(
            antenna.timestamp.iso8601,
            antenna.observedAzimuth,
            antenna.observedElevation,
            antenna.observedRightAscension,
            antenna.observedDeclination
        )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
