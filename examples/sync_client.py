#!/usr/bin/env python
from discos_client import DISCOSClient

def main():
    SRT = DISCOSClient(address='127.0.0.1')
    while True:
        antenna = SRT.get("antenna", wait=True)
        timestamp = SRT.get("antenna.timestamp")
        print(
            timestamp.iso8601,
            antenna.observedAzimuth,
            antenna.observedElevation,
            antenna.observedRightAscension,
            antenna.observedDeclination
        )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
