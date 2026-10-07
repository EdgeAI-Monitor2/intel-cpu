#!/usr/bin/env python3
"""
exporter.py
Converts monitoring samples into:
- CSV
- JSON
Adds:
- relative timestamps
- benchmark alignment
- experiment metadata
"""
import csv
import json
import time
class Exporter:
    def __init__(
        self,
        csv_file="trace.csv",
        json_file="trace.json"
    ):
        self.csv_file = csv_file
        self.json_file = json_file
    # ===============================
    # Timestamp alignment
    # ===================
    def align_timestamps(
        self,
        samples,
        benchmark_start
    ):

        aligned = []


        for sample in samples:


            item = {

                "timestamp":
                    sample["host_time"],


                "relative_time":
                    sample["host_time"]
                    -
                    benchmark_start,


                "state":
                    sample["state"],


                "sensor":
                    sample["sensor"],


                "tasmota":
                    sample["tasmota"]

            }


            aligned.append(item)


        return aligned



    # =====================================================
    # Flatten sample for CSV
    # =====================================================

    def flatten(self, sample):


        sensor = sample["sensor"]

        rapl = (
            sensor
            .get("rapl", {})
        )


        energy = (
            rapl
            .get("energy_j", {})
        )


        power = (
            rapl
            .get("power_w", {})
        )


        temp = (
            sensor
            .get("temperature", {})
        )


        freq = (
            sensor
            .get("frequency", {})
        )


        tasmota = (
            sample["tasmota"]
            or {}
        )


        return [

            sample["timestamp"],

            sample["relative_time"],

            sample["state"],


            # -----------------
            # Tasmota
            # -----------------

            tasmota.get(
                "power_w"
            ),

            tasmota.get(
                "voltage_v"
            ),

            tasmota.get(
                "current_a"
            ),

            tasmota.get(
                "power_factor"
            ),


            # -----------------
            # RAPL energy
            # -----------------

            energy.get(
                "package"
            ),

            energy.get(
                "core"
            ),

            energy.get(
                "uncore"
            ),

            energy.get(
                "psys"
            ),


            # -----------------
            # RAPL power
            # -----------------

            power.get(
                "package"
            ),

            power.get(
                "core"
            ),

            power.get(
                "uncore"
            ),

            power.get(
                "psys"
            ),


            # -----------------
            # Temperature
            # -----------------

            temp.get(
                "max_c"
            ),

            temp.get(
                "average_c"
            ),


            # -----------------
            # Frequency
            # -----------------

            freq.get(
                "average_mhz"
            ),

            freq.get(
                "min_mhz"
            ),

            freq.get(
                "max_mhz"
            ),


            # -----------------
            # CPU
            # -----------------

            sensor.get(
                "cpu_percent"
            ),

            sensor.get(
                "memory_percent"
            )

        ]
# =====================================================
    # Save CSV
    # =====================================================

    def save_csv(
        self,
        samples
    ):


        header = [

            "timestamp",

            "relative_time",

            "state",


            "wall_power_w",

            "voltage_v",

            "current_a",

            "power_factor",


            "package_energy_j",

            "core_energy_j",

            "uncore_energy_j",

            "psys_energy_j",

            "package_power_w",

            "core_power_w",

            "uncore_power_w",

            "psys_power_w",


            "max_temperature_c",

            "average_temperature_c",


            "average_frequency_mhz",

            "min_frequency_mhz",

            "max_frequency_mhz",


            "cpu_percent",

            "memory_percent"

        ]



        with open(
            self.csv_file,
            "w",
            newline=""
        ) as f:


            writer = csv.writer(f)


            writer.writerow(header)


            for sample in samples:

                writer.writerow(
                    self.flatten(sample)
                )



 # =====================================================
    # Save JSON
    # =====================================================

    def save_json(
        self,
        samples,
        metadata
    ):


        output = {


            "metadata":

                metadata,


            "samples":

                samples

        }


        with open(
            self.json_file,
            "w"
        ) as f:


            json.dump(
                output,
                f,
                indent=4
            )



    # =====================================================
    # Public API
    # =====================================================

    def save(
        self,
        samples,
        benchmark_start,
        benchmark_end
    ):


        aligned = self.align_timestamps(
            samples,
            benchmark_start
        )


        metadata = {


            "created":

                time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),


            "benchmark_start":

                benchmark_start,


            "benchmark_end":

                benchmark_end,


            "benchmark_duration_s":

                benchmark_end -
                benchmark_start,


            "total_samples":

                len(samples)

        }


        self.save_csv(
            aligned
        )


        self.save_json(
            aligned,
            metadata
        )


        print(
            "Export completed"
        )
