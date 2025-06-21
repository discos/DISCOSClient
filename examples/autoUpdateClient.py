#!/usr/bin/env python
from DISCOSClient import DISCOSClient
import time

if __name__ == '__main__':
    SRT = DISCOSClient(['mount'], address='192.168.10.200', auto_update=True)
    try:
        while True:
            print(SRT)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
