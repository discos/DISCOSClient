#!/usr/bin/env python
from discos_client import DISCOSClient

def main():
    #SRT = DISCOSClient(address='127.0.0.1', port='16001')
    SRT = DISCOSClient(address='192.168.10.200', port='16000')
    while True:
        antenna = SRT.get("antenna", wait=True)
        print(
            antenna.timestamp.iso8601,
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
