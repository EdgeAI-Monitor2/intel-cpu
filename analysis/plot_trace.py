#!/usr/bin/env python3
"""
plot_trace.py
Plot MLPerf benchmark-only monitoring data.
Input:
benchmark_samples.csv
Generated plots:
1. wall_power.png
2. package_power.png
3. temperature.png
4. cpu_utilization.png
5. memory_utilization.png
6. cpu_frequency.png
"""
import csv
import math
import matplotlib.pyplot as plt
INPUT_FILE = "benchmark_samples.csv"
# ===============================
# Load benchmark samples
# ==================
time = []
wall_power = []
package_power = []
temperature = []
cpu = []
memory = []
frequency = []
with open(INPUT_FILE, "r") as f:
    reader = csv.DictReader(f)

    for row in reader:

        try:
            timestamp = float(row["timestamp"])
        except (ValueError, TypeError):
            continue

        time.append(timestamp)

 # ------------------------------------
        # Tasmota wall power
        # ----------------------------------------------------

        try:
            wall_power.append(
                float(row["tasmota_power_w"])
            )
        except (ValueError, TypeError):
            wall_power.append(math.nan)

        # # RAPL package power
        # ----------------------------------------------------

        try:
            package_power.append(
                float(row["package_power_w"])
            )
        except (ValueError, TypeError):
            package_power.append(math.nan)
# -------------------
        # Temperature
        # ----------------------------------------
        try:
            temperature.append(
                float(row["temperature_max_c"])
            )
        except (ValueError, TypeError):
            temperature.append(math.nan)

        # -----------------------------
 # CPU utilization
       # ------------------------------

        try:
            cpu.append(
                float(row["cpu_percent"])
            )
        except (ValueError, TypeError):
            cpu.append(math.nan)

        # ----------------------------------------------------
      # Memory utilization
        # ----------------------------------------------------

        try:
            memory.append(
                float(row["memory_percent"])
            )
        except (ValueError, TypeError):
            memory.append(math.nan)

        # ----------------------------------------------------
        # CPU frequency
        # ----------------------------------------------------

        try:
            frequency.append(
                float(row["frequency_average_mhz"])
            )
        except (ValueError, TypeError):
            frequency.append(math.nan)
# ===========================================
# Convert time to benchmark-relative seconds
# =============================
if not time:
    print("ERROR: No benchmark samples found.")

    raise SystemExit(1)


start_time = time[0]

relative_time = [
    t - start_time
    for t in time
]


# ======================================
# Plot helper
# =================================

def make_plot(
    x,
    y,
    xlabel,
    ylabel,
    title,
    filename
):

    plt.figure(figsize=(12, 5))

    plt.plot(
        x,
        y,
        linewidth=1.5
    )

    plt.xlabel(xlabel)

    plt.ylabel(ylabel)

    plt.title(title)

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        filename,
        dpi=200
    )

    plt.close()

# ==========================================
# 1. Tasmota wall power
# ========================================

make_plot(
    relative_time,
    wall_power,
    "Benchmark Time (s)",
    "Wall Power (W)",
    "MLPerf Benchmark - Tasmota Wall Power",
    "wall_power.png"
)


# ============================================================
# 2. RAPL package power
# ============================================================

make_plot(
    relative_time,
    package_power,
    "Benchmark Time (s)",
    "Package Power (W)",
    "MLPerf Benchmark - Intel RAPL Package Power",
    "package_power.png"
)


# ============================================================
# 3. Temperature
# ============================================================

make_plot(
    relative_time,
    temperature,
    "Benchmark Time (s)",
    "Temperature (°C)",
    "MLPerf Benchmark - CPU Temperature",
    "temperature.png"
)


# ============================================================
# 4. CPU utilization
# ============================================================

make_plot(
    relative_time,
    cpu,
    "Benchmark Time (s)",
    "CPU Utilization (%)",
    "MLPerf Benchmark - CPU Utilization",
    "cpu_utilization.png"
)


# ============================================================
# 5. Memory utilization
# ============================================================

make_plot(
    relative_time,
    memory,
    "Benchmark Time (s)",
    "Memory Utilization (%)",
    "MLPerf Benchmark - Memory Utilization",
    "memory_utilization.png"
)


# ============================================================
# 6. CPU frequency
# ============================================================

make_plot(
    relative_time,
    frequency,
    "Benchmark Time (s)",
    "CPU Frequency (MHz)",
    "MLPerf Benchmark - CPU Frequency",
    "frequency.png"
)

# =============================
# Finished
# ================

print()

print("=" * 60)

print("MLPerf benchmark plots generated")

print("=" * 60)

print()

print("Input:")

print(f"  {INPUT_FILE}")

print()

print("Generated:")

print("  wall_power.png")

print("  package_power.png")
print("  temperature.png")
print("  cpu_utilization.png")
print("  memory_utilization.png")
print("  frequency.png")
print()
print(
    f"Benchmark samples plotted: "
    f"{len(relative_time)}"
)
print(
    f"Benchmark plotting duration: "
    f"{relative_time[-1]:.3f} s"
)
print()
