#!/usr/bin/env python3
"""
monitor.py
Monitoring thread.
Responsibilities
----------------
- Periodically sample all sensors
- Timestamp each sample
- Record the current experiment state (idle/preparation/benchmark/postprocess/cooldown)
- Store samples in memory
"""
import threading
import time
from sensors import SensorManager
from tasmota import TasmotaMonitor
class Monitor:
    def __init__(self, interval=1.0):
        self.interval = interval
        self.running = False
        self.state = "idle"
        self.samples = []
        self.lock = threading.Lock()
        # Initialize sensor managers
        self.sensors = SensorManager()

        self.tasmota = TasmotaMonitor()
    # ------------------------------------
    def set_state(self, state):
        """
        Current execution phase.
idle/preparation/benchmark/postprocess/cooldown
        """
        with self.lock:
            self.state = state
    # ----------------------------------------------------
    def stop(self):

        self.running = False

    # ----------------------------------------------------

    def run(self):

        """
        Main monitoring loop.
        """

        self.running = True

        while self.running:

            host_time = time.time()

            with self.lock:
                current_state = self.state

            # -----------------------------
            # Intel/NVIDIA sensors
            # -----------------------------

            sensor_data = self.sensors.read_all()

            # -----------------------------
            # External wall power: Refoss P11 Power Monitoring Plug (P11)
            # -----------------------------

            tasmota_data = self.tasmota.read()

            sample = {

                "host_time": host_time,

                "state": current_state,

                "sensor": sensor_data,

                "tasmota": tasmota_data

            }

            self.samples.append(sample)

            time.sleep(self.interval)
