#!/usr/bin/env python
from DISCOSClient import DISCOSClient

if __name__ == '__main__':
    SRT = DISCOSClient('mount', address='192.168.10.200', port='16000')
    try:
        while True:
            print(
                f'{SRT.mount.timestamp.iso8601}',
                f'{SRT.mount.azimuth.currentPosition:>12.6f}',
                f'{SRT.mount.elevation.currentPosition:>12.6f}',
                f'{SRT.mount.azimuth.currentRate:>12.6f}',
                f'{SRT.mount.elevation.currentRate:>12.6f}'
            )
            SRT.wait_for_update('mount')
    except KeyboardInterrupt:
        pass
