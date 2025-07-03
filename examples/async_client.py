#!/usr/bin/env python
import asyncio
from discos_client import DISCOSClient

async def main():
    SRT = DISCOSClient(address='192.168.10.200', port='16000', asyncronous=True)
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
