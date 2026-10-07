#!/usr/bin/env python3
"""
tasmota.py
Tasmota power monitor interface.
Collects:
- AC power (W)
- Voltage (V)
- Current (A)
- Apparent power (VA)
- Reactive power (VAR)
- Power factor
- Tasmota timestamp
Also estimates clock offset between:
- NUC host clock
- Tasmota clock
Used by monitor.py
"""
import time
import requests
from datetime import datetime
class TasmotaMonitor:
    def __init__(
        self,
        ip="192.168.101.219",
        timeout=2
    ):

        self.ip = ip

        self.timeout = timeout


        # NUC - Tasmota clock offset

        self.clock_offset = None


        # Last successful sample

        self.last_sample = None
    # ==================================
    # Query Tasmota
    # =======================
    def query(self):
        url = (
            f"http://{self.ip}"
            "/cm?cmnd=Status%208"
        )
        host_before = time.time()
        try:
            response = requests.get(
                url,
                timeout=self.timeout
            )


            host_after = time.time()


            data = response.json()


        except Exception:

            return None

        # Estimate request midpoint

        host_mid = (
            host_before +
            host_after
        ) / 2

        return data, host_mid
    # ======================================
    # Parse Tasmota response
    # ========================
    def parse(self, raw, host_time):
        try:
            status = raw["StatusSNS"]

            energy = status["ENERGY"]


        except Exception:

            return None



        tasmota_time = (
            status.get(
                "Time",
                None
            )
        )


        # -------------------------
        # Clock synchronization
        # -------------------------

        if tasmota_time:


            try:

                t_time = datetime.strptime(
                    tasmota_time,
                    "%Y-%m-%dT%H:%M:%S"
                )


                t_epoch = (
                    t_time.timestamp()
                )


                self.clock_offset = (
                    host_time -
                    t_epoch
                )


            except Exception:

                pass



        # -------------------------
        # Return normalized data
        # -------------------------

        return {


            "host_time":
                host_time,


            "tasmota_time":
                tasmota_time,


            "clock_offset":
                self.clock_offset,


            "power_w":
                energy.get(
                    "Power"
                ),


            "voltage_v":
                energy.get(
                    "Voltage"
                ),


            "current_a":
                energy.get(
                    "Current"
                ),


            "apparent_va":
                energy.get(
                    "ApparentPower"
                ),


            "reactive_var":
                energy.get(
                    "ReactivePower"
                ),


            "power_factor":
                energy.get(
                    "Factor"
                )

        }
    # ================================
    # Public API
    # ================
    def read(self):

        result = self.query()


        if result is None:

            return {

                "power_w": None,

                "voltage_v": None,

                "current_a": None,

                "clock_offset": self.clock_offset

            }


        raw, host_time = result


        sample = self.parse(
            raw,
            host_time
        )


        if sample:

            self.last_sample = sample


        return sample
