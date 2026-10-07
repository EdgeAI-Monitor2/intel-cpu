#!/usr/bin/env python3
"""
sensors.py
Hardware monitoring backend.
Supports:
- Intel RAPL
- CPU temperatures
- CPU frequency
- CPU utilization
- Memory utilization
The module is CPU vendor dependent.
For NVIDIA Orin, this file can later be replaced
with INA3221 / tegrastats monitoring.
"""
import os
import glob
import time
import psutil
class SensorManager:
    def __init__(self):
        # --------------------
        # RAPL
        # -----------------------------
        self.rapl_paths = self.detect_rapl()
        self.previous_energy = {}
        self.previous_time = None


        # -----------------------------
        # Temperature
        # -----------------------------

        self.temperature_paths = (
            self.detect_temperatures()
        )


        # -----------------------------
        # CPU frequency
        # -----------------------------

        self.frequency_paths = (
            self.detect_frequency()
        )



    # =====================================================
    # RAPL detection
    # =====================================================

    def detect_rapl(self):

        rapl = {}

        base = "/sys/class/powercap"

        if not os.path.exists(base):
            return rapl


        for path in glob.glob(
            base + "/intel-rapl*/energy_uj"
        ):

            name = path.split("/")[-2]

            if name == "intel-rapl:0":
                rapl["package"] = path

            elif name == "intel-rapl:1":
                rapl["psys"] = path


        # subdomains

        for path in glob.glob(
            base + "/intel-rapl:0:* /energy_uj"
        ):

            pass


        # Explicit search for subdomains

        for path in glob.glob(
            base + "/intel-rapl:0:*"
        ):

            energy = path + "/energy_uj"

            if os.path.exists(energy):

                if ":0:0" in path:
                    rapl["core"] = energy

                elif ":0:1" in path:
                    rapl["uncore"] = energy


        return rapl



    # =====================================================
    # Temperature detection
    # =====================================================

    def detect_temperatures(self):

        paths = []

        # Linux thermal zones

        paths.extend(
            glob.glob(
                "/sys/class/thermal/thermal_zone*/temp"
            )
        )


        # hwmon fallback

        paths.extend(
            glob.glob(
                "/sys/class/hwmon/hwmon*/temp*_input"
            )
        )


        return paths



    # =====================================================
    # CPU frequency detection
    # =====================================================

    def detect_frequency(self):

        return sorted(
            glob.glob(
                "/sys/devices/system/cpu/"
                "cpu*/cpufreq/scaling_cur_freq"
            )
        )



    # =====================================================
    # Safe integer reader
    # =====================================================

    def read_int(self, path):

        try:

            with open(path) as f:
                return int(
                    f.read().strip()
                )

        except Exception:

            return None



    # =====================================================
    # RAPL reading
    # =====================================================

    def read_rapl(self):

        now = time.time()

        energy = {}

        power = {}


        for name, path in self.rapl_paths.items():

            value = self.read_int(path)


            if value is None:
                continue


            # micro Joule -> Joule

            joules = value / 1e6

            energy[name] = joules



            # -----------------------------
            # Power calculation
            # -----------------------------

            if (
                self.previous_time is not None
                and name in self.previous_energy
            ):

                dt = now - self.previous_time


                delta = (
                    joules -
                    self.previous_energy[name]
                )


                # RAPL overflow protection

                if delta < 0:

                    delta = 0


                power[name] = (
                    delta / dt
                )


            else:

                power[name] = None



        self.previous_energy = energy

        self.previous_time = now


        return {

            "energy_j": energy,

            "power_w": power

        }



    # =====================================================
    # Temperatures
    # =====================================================

    def read_temperature(self):

        values = []


        for path in self.temperature_paths:

            value = self.read_int(path)


            if value is None:
                continue


            # Most Linux sensors use millidegree Celsius

            if value > 1000:

                value = value / 1000


            values.append(value)



        if not values:

            return {

                "max_c": None,
                "average_c": None

            }



        return {

            "max_c": max(values),

            "average_c":
                sum(values) / len(values)

        }



    # =====================================================
    # Frequency
    # =====================================================

    def read_frequency(self):

        values = []


        for path in self.frequency_paths:

            value = self.read_int(path)


            if value:

                # kHz -> MHz

                values.append(
                    value / 1000
                )



        if not values:

            return {

                "average_mhz": None,
                "min_mhz": None,
                "max_mhz": None

            }



        return {

            "average_mhz":
                sum(values)/len(values),

            "min_mhz":
                min(values),

            "max_mhz":
                max(values)

        }



    # =====================================================
    # Complete sensor read
    # =====================================================

    def read_all(self):


        rapl = self.read_rapl()

        temp = self.read_temperature()

        freq = self.read_frequency()


        cpu = psutil.cpu_percent()

        memory = psutil.virtual_memory()


        load = os.getloadavg()



        return {


            "rapl": rapl,
            "temperature": temp,
            "frequency": freq,
            "cpu_percent": cpu,
            "memory_percent":
                memory.percent,
            "load": {
                "1min": load[0],
                "5min": load[1],
                "15min": load[2]
            }
        }
