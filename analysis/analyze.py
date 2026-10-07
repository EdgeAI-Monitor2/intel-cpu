#!/usr/bin/env python3
"""
analyze.py
Analyze MLPerf monitoring data from trace.json.
Only samples inside the exact MLPerf benchmark interval are used:
benchmark_start <= timestamp <= benchmark_end
Calculates:
- Benchmark duration
- RAPL PSYS energy
- RAPL package energy
- RAPL core energy
- RAPL uncore energy
- Average / maximum CPU temperature
- Average / maximum system temperature
- Average / maximum CPU utilization
- Average / maximum memory utilization
- Average CPU frequency
- Average / maximum RAPL package power
- Average / maximum Tasmota wall power
- Tasmota wall energy
- Average voltage
- Average current
- Average power factor
Outputs:
1. Clean MLPerf measurement table
2. benchmark_samples.csv
3. benchmark_summary.json
"""
import json
import csv
import os
import statistics
# ===========================
# Configuration
# ====================
TRACE_FILE = "trace.json"
BENCHMARK_SAMPLES_FILE = "benchmark_samples.csv"
SUMMARY_FILE = "benchmark_summary.json"
# ===================
# Helper functions
# ====================
def to_float(value):
    """Convert a value to float, returning None if unavailable."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None
def values(rows, key):
    """Return all valid numeric values for a CSV-style key."""
    result = []

    for row in rows:
        value = to_float(row.get(key))

        if value is not None:
            result.append(value)
    return result
def nested_value(sample, *keys):
 """    Safely retrieve a nested value.
    Example:
 nested_value(sample, "sensor", "temperature", "max_c")
    """
    value = sample
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
        if value is None:
            return None
    return to_float(value)
def statistics_for(samples, *keys):
    """Return average and maximum for a nested measurement."""
    data = []
    for sample in samples:
        value = nested_value(sample, *keys)
        if value is not None:
            data.append(value)
    if not data:
        return None, None

    return statistics.mean(data), max(data)
def first_value(samples, *keys):
    """Get first valid value."""

    for sample in samples:

        value = nested_value(sample, *keys)

        if value is not None:
            return value

    return None


def last_value(samples, *keys):
    """Get last valid value."""

    for sample in reversed(samples):

        value = nested_value(sample, *keys)

        if value is not None:
            return value

    return None


def energy_difference(samples, *keys):
    """
    Calculate energy consumed during benchmark.

    Energy meters are cumulative, therefore:

        energy = last - first
    """

    first = first_value(samples, *keys)
    last = last_value(samples, *keys)

    if first is None or last is None:
        return None

    energy = last - first

    # Protect against counter resets.
    if energy < 0:
        return None

    return energy


def integrate_power(samples, power_keys):
    """
    Calculate energy from power measurements using trapezoidal integration.
    It is significant for Tasmota because the Tasmota power field is
    instantaneous power rather than a cumulative energy counter.
    Returns Joules.
    """

    points = []

    for sample in samples:

        timestamp = to_float(sample.get("timestamp"))

        power = nested_value(
            sample,
            *power_keys
        )

        if timestamp is not None and power is not None:
            points.append((timestamp, power))

    if len(points) < 2:
        return None

    points.sort(key=lambda x: x[0])

    energy = 0.0

    for i in range(1, len(points)):

        t1, p1 = points[i - 1]
        t2, p2 = points[i]

        dt = t2 - t1

        if dt <= 0:
            continue

   # Trapezoidal integration:
             # E = average(P1,P2) * dt
        energy += ((p1 + p2) / 2.0) * dt

    return energy


def fmt(value, decimals=3, unit=""):
    """Format a number for the output table."""

    if value is None:
        return "N/A"

    return f"{value:.{decimals}f}{unit}"
# =======================
# Load trace.json
# ===================
if not os.path.exists(TRACE_FILE):

    print(f"ERROR: {TRACE_FILE} was not found.")
    raise SystemExit(1)
with open(TRACE_FILE, "r") as f:
    data = json.load(f)
metadata = data.get("metadata", {})
samples = data.get("samples", [])
if not samples:
    print("ERROR: trace.json contains no samples.")
    raise SystemExit(1)
# =================================
# Benchmark timestamps
# ==========================
benchmark_start = to_float(
    metadata.get("benchmark_start")
)

benchmark_end = to_float(
    metadata.get("benchmark_end")
)


if benchmark_start is None or benchmark_end is None:

    print(
        "ERROR: benchmark_start or benchmark_end "
        "is missing from trace.json."
    )
    raise SystemExit(1)
benchmark_duration = benchmark_end - benchmark_start
if benchmark_duration <= 0:

    print("ERROR: benchmark duration is not positive.")

    raise SystemExit(1)
# ==================================
# Select ONLY benchmark samples
# ===========
benchmark_samples = []
for sample in samples:
    timestamp = to_float(
        sample.get("timestamp")
    )

    if timestamp is None:
        continue

    if (
        timestamp >= benchmark_start
        and
        timestamp <= benchmark_end
    ):

        benchmark_samples.append(sample)
# Fallback using state if timestamp filtering somehow fails.
if not benchmark_samples:
    benchmark_samples = [
        sample
        for sample in samples
        if sample.get("state") == "benchmark"
    ]
if not benchmark_samples:
    print(
        "ERROR: No benchmark samples were found."
    )
    raise SystemExit(1)
# Sort chronologically.
benchmark_samples.sort(
    key=lambda x: to_float(x.get("timestamp")) or 0
)
# ====================
# RAPL ENERGY
# =============
psys_energy = energy_difference(
    benchmark_samples,
    "sensor",
    "rapl",
    "energy_j",
    "psys"
)
package_energy = energy_difference(
    benchmark_samples,
    "sensor",
    "rapl",
    "energy_j",
    "package"
)
core_energy = energy_difference(
    benchmark_samples,
    "sensor",
    "rapl",
    "energy_j",
    "core"
)
uncore_energy = energy_difference(
    benchmark_samples,
    "sensor",
    "rapl",
    "energy_j",
    "uncore"
)
# ==================
# TEMPERATURE
# ============
avg_temperature, max_temperature = statistics_for(
    benchmark_samples,
    "sensor",
    "temperature",
    "average_c"
)
avg_temperature_max_sensor, max_temperature_sensor = statistics_for(
    benchmark_samples,
    "sensor",
    "temperature",
    "max_c"
)
# ===================
# CPU UTILIZATION
# =============
avg_cpu_utilization, max_cpu_utilization = statistics_for(
    benchmark_samples,
    "sensor",
    "cpu_percent"
)
# ==============
# MEMORY UTILIZATION
# ======================
avg_memory_utilization, max_memory_utilization = statistics_for(
    benchmark_samples,
    "sensor",
    "memory_percent"
)
# =================
# CPU FREQUENCY
# ==========
avg_cpu_frequency, max_cpu_frequency = statistics_for(
    benchmark_samples,
    "sensor",
    "frequency",
    "average_mhz"
)
# =======================================
# RAPL PACKAGE POWER
# =============================
avg_package_power, max_package_power = statistics_for(
    benchmark_samples,
    "sensor",
    "rapl",
    "power_w",
    "package"
)
# ==========================
# RAPL PSYS POWER
# ==============================
avg_psys_power, max_psys_power = statistics_for(
    benchmark_samples,
    "sensor",
    "rapl",
    "power_w",
    "psys"
)
# =================================
# TASMOTA WALL POWER
# =============================
avg_tasmota_power, max_tasmota_power = statistics_for(
    benchmark_samples,
    "tasmota",
    "power_w"
)
avg_tasmota_voltage, max_tasmota_voltage = statistics_for(
    benchmark_samples,
    "tasmota",
    "voltage_v"
)
avg_tasmota_current, max_tasmota_current = statistics_for(
    benchmark_samples,
    "tasmota",
    "current_a"
)
avg_tasmota_power_factor, max_tasmota_power_factor = statistics_for(
    benchmark_samples,
    "tasmota",
    "power_factor"
)
# ============================
# TASMOTA WALL ENERGY
# ================
tasmota_energy_j = integrate_power(
    benchmark_samples,
    (
        "tasmota",
        "power_w"
    )
)
tasmota_energy_wh = None
if tasmota_energy_j is not None:
    tasmota_energy_wh = (
        tasmota_energy_j / 3600.0
    )
# ================================
# RAPL ENERGY IN Wh
# ======================
package_energy_wh = None
if package_energy is not None:
    package_energy_wh = (
        package_energy / 3600.0
    )
psys_energy_wh = None
if psys_energy is not None:
    psys_energy_wh = (
        psys_energy / 3600.0
    )
# =================
# Create benchmark_samples.csv
# ================================
csv_fields = [
    "timestamp",
    "relative_time",
    "state",
    "psys_energy_j",
    "package_energy_j",
    "core_energy_j",
    "uncore_energy_j",
    "psys_power_w",
    "package_power_w",
    "temperature_average_c",
    "temperature_max_c",
    "cpu_percent",
    "memory_percent",
    "frequency_average_mhz",
    "tasmota_power_w",
    "tasmota_voltage_v",
    "tasmota_current_a",
    "tasmota_power_factor",
]
with open(
    BENCHMARK_SAMPLES_FILE,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=csv_fields
    )

    writer.writeheader()

    for sample in benchmark_samples:

        row = {

            "timestamp":
                sample.get("timestamp"),

            "relative_time":
                sample.get("relative_time"),

            "state":
                sample.get("state"),

            "psys_energy_j":
                nested_value(
                    sample,
                    "sensor",
                    "rapl",
                    "energy_j",
                    "psys"
                ),

            "package_energy_j":
                nested_value(
                    sample,
                    "sensor",
                    "rapl",
                    "energy_j",
                    "package"
                ),

            "core_energy_j":
                nested_value(
                    sample,
                    "sensor",
                    "rapl",
                    "energy_j",
                    "core"
                ),

            "uncore_energy_j":
                nested_value(
                    sample,
                    "sensor",
                    "rapl",
                    "energy_j",
                    "uncore"
                ),

            "psys_power_w":
                nested_value(
                    sample,
                    "sensor",
                    "rapl",
                    "power_w",
                    "psys"
                ),

            "package_power_w":
                nested_value(
                    sample,
                    "sensor",
                    "rapl",
                    "power_w",
                    "package"
                ),

            "temperature_average_c":
                nested_value(
                    sample,
                    "sensor",
                    "temperature",
                    "average_c"
                ),

            "temperature_max_c":
                nested_value(
                    sample,
                    "sensor",
                    "temperature",
                    "max_c"
                ),

            "cpu_percent":
                nested_value(
                    sample,
                    "sensor",
                    "cpu_percent"
                ),

            "memory_percent":
                nested_value(
                    sample,
                    "sensor",
                    "memory_percent"
                ),

            "frequency_average_mhz":
                nested_value(
                    sample,
                    "sensor",
                    "frequency",
                    "average_mhz"
                ),

            "tasmota_power_w":
                nested_value(
                    sample,
                    "tasmota",
                    "power_w"
                ),

            "tasmota_voltage_v":
                nested_value(
                    sample,
                    "tasmota",
                    "voltage_v"
                ),

            "tasmota_current_a":
                nested_value(
                    sample,
                    "tasmota",
                    "current_a"
                ),

            "tasmota_power_factor":
                nested_value(
                    sample,
                    "tasmota",
                    "power_factor"
                ),
        }
        writer.writerow(row)
# ===========================
# Summary JSON
# =====================
summary = {
    "benchmark": {
        "start_timestamp":
            benchmark_start,
        "end_timestamp":
            benchmark_end,
        "duration_s":
            benchmark_duration,
        "samples":
            len(benchmark_samples),
    },
    "rapl": {
        "psys_energy_j":
            psys_energy,
        "psys_energy_wh":
            psys_energy_wh,

        "package_energy_j":
            package_energy,

        "package_energy_wh":
            package_energy_wh,

        "core_energy_j":
            core_energy,

        "uncore_energy_j":
            uncore_energy,

        "average_psys_power_w":
            avg_psys_power,

        "maximum_psys_power_w":
            max_psys_power,

        "average_package_power_w":
            avg_package_power,

        "maximum_package_power_w":
            max_package_power,
    },

    "temperature": {

        "average_c":
            avg_temperature,

        "maximum_average_sensor_c":
            max_temperature,

        "average_of_max_sensor_c":
            avg_temperature_max_sensor,

        "maximum_sensor_temperature_c":
            max_temperature_sensor,
    },

    "cpu": {

        "average_utilization_percent":
            avg_cpu_utilization,

        "maximum_utilization_percent":
            max_cpu_utilization,

        "average_frequency_mhz":
            avg_cpu_frequency,

        "maximum_frequency_mhz":
            max_cpu_frequency,
    },

    "memory": {

        "average_utilization_percent":
            avg_memory_utilization,

        "maximum_utilization_percent":
            max_memory_utilization,
    },

    "tasmota": {

        "average_power_w":
            avg_tasmota_power,

        "maximum_power_w":
            max_tasmota_power,

        "wall_energy_j":
            tasmota_energy_j,

        "wall_energy_wh":
            tasmota_energy_wh,

        "average_voltage_v":
            avg_tasmota_voltage,

        "average_current_a":
            avg_tasmota_current,

        "average_power_factor":
            avg_tasmota_power_factor,
    },
}


with open(
    SUMMARY_FILE,
    "w"
) as f:

    json.dump(
        summary,
        f,
        indent=4
    )
# ======================
# PRINT CLEAN MLPerf TABLE
# =====================
print()
print("=" * 78)
print("MLPerf BENCHMARK MEASUREMENT")
print("=" * 78)

print()

print(
    f"{'Metric':<48}"
    f"{'Value':>20}"
)

print("-" * 78)


# -----------------------------
# Benchmark
# -----------------
print(
    f"{'Benchmark duration':<48}"
    f"{fmt(benchmark_duration, 3, ' s'):>20}"
)
print(
    f"{'Benchmark samples':<48}"
    f"{len(benchmark_samples):>20}"
)
print("-" * 78)
# -----------------------------------
# RAPL
# -------------------------
print(
    f"{'RAPL PSYS energy':<48}"
    f"{fmt(psys_energy, 3, ' J'):>20}"
)
print(
    f"{'RAPL package energy':<48}"
    f"{fmt(package_energy, 3, ' J'):>20}"
)
print(
    f"{'RAPL package energy':<48}"
    f"{fmt(package_energy_wh, 6, ' Wh'):>20}"
)

print(
    f"{'RAPL core energy':<48}"
    f"{fmt(core_energy, 3, ' J'):>20}"
)

print(
    f"{'RAPL uncore energy':<48}"
    f"{fmt(uncore_energy, 3, ' J'):>20}"
)

print(
    f"{'Average RAPL package power':<48}"
    f"{fmt(avg_package_power, 3, ' W'):>20}"
)

print(
    f"{'Maximum RAPL package power':<48}"
    f"{fmt(max_package_power, 3, ' W'):>20}"
)
print("-" * 78)
# -------------------------------------
# Temperature
# ---------------------
print(
    f"{'Average temperature':<48}"
    f"{fmt(avg_temperature, 2, ' °C'):>20}"
)
print(
    f"{'Maximum temperature':<48}"
    f"{fmt(max_temperature_sensor, 2, ' °C'):>20}"
)

print("-" * 78)
# ---------------------------
# CPU
# ------------------
print(
    f"{'Average CPU utilization':<48}"
    f"{fmt(avg_cpu_utilization, 2, ' %'):>20}"
)
print(
    f"{'Maximum CPU utilization':<48}"
    f"{fmt(max_cpu_utilization, 2, ' %'):>20}"
)
print(
    f"{'Average CPU frequency':<48}"
    f"{fmt(avg_cpu_frequency, 2, ' MHz'):>20}"
)

print(
    f"{'Maximum CPU frequency':<48}"
    f"{fmt(max_cpu_frequency, 2, ' MHz'):>20}"
)
print("-" * 78)
# -------------------
# Memory
# ------------------------------
print(
    f"{'Average memory utilization':<48}"
    f"{fmt(avg_memory_utilization, 2, ' %'):>20}"
)
print(
    f"{'Maximum memory utilization':<48}"
    f"{fmt(max_memory_utilization, 2, ' %'):>20}"
)
print("-" * 78)
# ----------------------------
# Tasmota wall measurement
# --------------------
print(
    f"{'Average Tasmota wall power':<48}"
    f"{fmt(avg_tasmota_power, 3, ' W'):>20}"
)
print(
    f"{'Maximum Tasmota wall power':<48}"
    f"{fmt(max_tasmota_power, 3, ' W'):>20}"
)

print(
    f"{'Tasmota wall energy':<48}"
    f"{fmt(tasmota_energy_j, 3, ' J'):>20}"
)

print(
    f"{'Tasmota wall energy':<48}"
    f"{fmt(tasmota_energy_wh, 6, ' Wh'):>20}"
)

print(
    f"{'Average Tasmota voltage':<48}"
    f"{fmt(avg_tasmota_voltage, 2, ' V'):>20}"
)

print(
    f"{'Average Tasmota current':<48}"
    f"{fmt(avg_tasmota_current, 4, ' A'):>20}"
)
print(
    f"{'Average power factor':<48}"
    f"{fmt(avg_tasmota_power_factor, 3):>20}"
)
print("=" * 78)
print()
print(
    f"Benchmark samples saved to: {BENCHMARK_SAMPLES_FILE}"
)
print(
    f"Summary saved to:           {SUMMARY_FILE}"
)
print()
