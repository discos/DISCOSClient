#!/usr/bin/env python
import tkinter as tk
from datetime import datetime
from threading import Thread
import time
from discos_client import DISCOSClient


class AntennaGUI:
    def __init__(self, root, client):
        self.client = client

        self.timestamp_label = tk.Label(root, text="Timestamp: ")
        self.timestamp_label.pack()

        self.az_label = tk.Label(root, text="Raw Azimuth: ")
        self.az_label.pack()

        self.el_label = tk.Label(root, text="Raw Elevation: ")
        self.el_label.pack()

        self.update_thread = Thread(target=self.poll_data, daemon=True)
        self.update_thread.start()

    def poll_data(self):
        while True:
            antenna = self.client.get("antenna", wait=True)
            self.timestamp_label.after(0, lambda: self.timestamp_label.config(text=f"Timestamp: {antenna.timestamp.iso8601}"))
            self.az_label.after(0, lambda: self.az_label.config(text=f"Raw Azimuth: {antenna.rawAzimuth}"))
            self.el_label.after(0, lambda: self.el_label.config(text=f"Raw Elevation: {antenna.rawElevation}"))


if __name__ == "__main__":
    SRT = DISCOSClient("antenna", address='127.0.0.1')
    root = tk.Tk()
    root.title("Antenna Monitor")
    gui = AntennaGUI(root, SRT)
    root.mainloop()
