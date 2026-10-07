#!/usr/bin/env python3

"""
wrapper.py

MLPerf monitoring wrapper utlising pexpect.

Flow:

1. Measure idle period
2.Begin monitoring
3. Launch MLPerf Docker interactive shell
4. Wait for Docker prompt
5. Run MLPerf performance-only command INSIDE Docker
6. Wait for the NEW valid_results MLPerf log
7. Begin MLPerf log watcher
8. Detect benchmark start/end
9. Wait for MLPerf command to end
10. Exit Docker
11. Measure cooldown
12. Export CSV + JSON
"""

import argparse
import threading
import pexpect
import time
import glob
import os
import sys
from log_watcher import MLPerfLogWatcher
from monitor import Monitor
from exporter import Exporter


# ==========================================================
# ARGUMENTS
# ==========================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description="MLPerf Monitoring Wrapper"
    )

    parser.add_argument(
        "--idle",
        type=int,
        default=30,
        help="Idle measurement before benchmark (seconds)"
    )

    parser.add_argument(
        "--cooldown",
        type=int,
        default=20,
        help="Cool-down measurement after benchmark (seconds)"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Sampling interval (seconds)"
    )

    parser.add_argument(
        "--csv",
        default="trace.csv",
        help="CSV output filename"
    )

    parser.add_argument(
        "--json",
        default="trace.json",
        help="JSON output filename"
    )

    parser.add_argument(
        "--cmd",
        nargs=argparse.REMAINDER,
        required=True,
        help="MLPerf Docker launch command"
    )

    return parser.parse_args()


# ==============================================
# FIND MLPerf LOGS
# ===================================

def get_mlperf_logs():

    pattern = (
        "/home/*/MLC/repos/local/cache/**/"
        "valid_results/**/"
        "resnet50/**/"
        "offline/performance/run_*/"
        "mlperf_log_detail.txt"
    )

    logs = glob.glob(
        pattern,
        recursive=True
    )

    return logs


def get_log_mtime(log_path):

    try:
        return os.path.getmtime(log_path)
    except OSError:
        return 0


def snapshot_mlperf_logs():

    """
    Take a snapshot of all existing valid performance logs.

    We use this to distinguish the NEW performance run
    from older MLPerf logs.
    """

    logs = get_mlperf_logs()

    snapshot = {}

    for log in logs:

        try:

            snapshot[log] = os.path.getmtime(log)

        except OSError:

            pass

    return snapshot


def find_new_mlperf_log(
    old_snapshot,
    timeout=180
):

    """
    Wait for a NEW or newly modified MLPerf performance log.
    The performance-only command can take some time before
    creating/updating mlperf_log_detail.txt.

    So we do NOT simply use "mtime > search_start"
    because the Docker preparation and file creation timing
    can make that unreliable.
    """

    print(
        "\n[Wrapper] Searching for NEW MLPerf "
        "performance log..."
    )

    start = time.time()

    while True:

        logs = get_mlperf_logs()

        candidates = []

        for log in logs:

            try:

                current_mtime = os.path.getmtime(log)

            except OSError:

                continue

            old_mtime = old_snapshot.get(log)

            # --------------------------------------------------
            # Entirely new log
            # --------------------------------------------------

            if old_mtime is None:

                candidates.append(log)

            # --------------------------------------------------
            # Existing log that was modified
            # --------------------------------------------------

            elif current_mtime > old_mtime:

                candidates.append(log)

        if candidates:

            newest = max(
                candidates,
                key=get_log_mtime
            )

            print(
                "\n[Wrapper] NEW MLPerf performance log found:"
            )

            print(newest)

            return newest

        # ------------------------------------------------------
        # Timeout
        # ------------------------------------------------------

        if time.time() - start > timeout:

            print(
                "\nERROR: Timeout while waiting for "
                "new MLPerf performance log."
            )

            print(
                "\nExisting MLPerf logs:"
            )

            for log in sorted(
                get_mlperf_logs(),
                key=get_log_mtime
            ):

                print(
                    f"  {get_log_mtime(log):.3f}  {log}"
                )

            return None

        time.sleep(0.5)


# ==========================================================
# DOCKER PROMPT
# ==========================================================

def wait_for_docker_prompt(child):

    """
    Wait for the interactive Docker shell prompt.

    Example:

        ubuntu@e3efb7d373e6:~$

    """

    print(
        "\n[Wrapper] Waiting for Docker interactive shell..."
    )

    try:

        child.expect(
            r"ubuntu@[^:\r\n]+:~\$",
            timeout=1800
        )

        print(
            "\n[Wrapper] Docker interactive shell detected."
        )

        return True

    except pexpect.TIMEOUT:

        print(
            "\nERROR: Docker shell prompt was not detected."
        )

        return False

    except pexpect.EOF:

        print(
            "\nERROR: Docker process terminated "
            "before shell prompt appeared."
        )

        return False


# ==========================================================
# WAIT FOR DOCKER COMMAND TO end
# ==========================================================

def wait_for_shell_prompt(child):

    """
    Wait until the performance-only command returns to
    the Docker shell.

    Important:
    We do not use child.isalive() to determine benchmark
    completion because the Docker shell itself stays alive.
    """

    print(
        "\n[Wrapper] Waiting for MLPerf command "
        "to return to Docker shell..."
    )

    try:

        child.expect(
            r"ubuntu@[^:\r\n]+:~\$",
            timeout=None
        )

        print(
            "\n[Wrapper] MLPerf command returned "
            "to Docker shell."
        )

        return True

    except pexpect.EOF:

        print(
            "\nERROR: Docker shell exited unexpectedly."
        )

        return False

    except pexpect.TIMEOUT:

        print(
            "\nERROR: Timeout waiting for Docker shell."
        )

        return False


# ==========================================================
# EXIT DOCKER
# ==========================================================

def exit_docker(child):

    print(
        "\n[Wrapper] Exiting Docker container..."
    )

    try:

        child.sendline("exit")

        child.expect(
            pexpect.EOF,
            timeout=30
        )

        print(
            "\n[Wrapper] Docker container exited."
        )

    except pexpect.TIMEOUT:

        print(
            "\nWARNING: Docker did not exit normally."
        )

        child.close(
            force=True
        )

    except pexpect.EOF:

        pass


# ==========================================================
# MAIN
# ==========================================================

def main():

    args = parse_args()

    print("=" * 60)
    print("EdgeAI-Monitor Framework")
    print("=" * 60)

    print(
        "\nDocker launch command:"
    )

    print(
        " ".join(args.cmd)
    )

    # ======================================================
    # MONITOR
    # ======================================================

    monitor = Monitor(
        interval=args.interval
    )

    monitor_thread = threading.Thread(
        target=monitor.run,
        daemon=True
    )

    # ======================================================
    # IDLE
    # ======================================================

    print(
        "\nIdle measurement..."
    )

    monitor.set_state(
        "idle"
    )

    monitor_thread.start()

    time.sleep(
        args.idle
    )

    # ======================================================
    # SNAPSHOT EXISTING MLPerf LOGS
    # ======================================================

    print(
        "\n[Wrapper] Taking snapshot of existing "
        "MLPerf performance logs..."
    )

    old_log_snapshot = snapshot_mlperf_logs()

    print(
        f"[Wrapper] Existing performance logs: "
        f"{len(old_log_snapshot)}"
    )

    # ======================================================
    # LAUNCH DOCKER
    # ======================================================

    print(
        "\nLaunching MLPerf Docker container..."
    )

    monitor.set_state(
        "preparation"
    )

    docker_cmd = " ".join(
        args.cmd
    )

    print(
        "\nStarting:"
    )

    print(
        docker_cmd
    )

    try:

        child = pexpect.spawn(
            docker_cmd,
            encoding="utf-8",
            timeout=None
        )

    except Exception as e:

        print(
            "\nERROR: Could not start Docker:"
        )

        print(e)

        monitor.stop()
        monitor_thread.join()

        sys.exit(1)

    # Show Docker output on terminal
    child.logfile = sys.stdout

    # ======================================================
    # WAIT FOR DOCKER SHELL
    # ======================================================

    if not wait_for_docker_prompt(
        child
    ):

        child.close(
            force=True
        )

        monitor.stop()
        monitor_thread.join()

        sys.exit(1)

    # ===================================
    # PERFORMANCE-ONLY COMMAND
    # ======================

    performance_cmd = (
        "mlcr "
        "run-mlperf,inference,_full,_r5.1-dev,"
        "_performance-only "
        "--model=resnet50 "
        "--implementation=reference "
        "--framework=onnxruntime "
        "--category=edge "
        "--scenario=Offline "
        "--execution_mode=valid "
        "--device=cpu "
        "--quiet"
       # "--threads=6"
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "Starting MLPerf performance-only benchmark"
    )

    print(
        "INSIDE Docker container"
    )

    print(
        "=" * 60
    )

    print(
        "\nCommand:"
    )

    print(
        performance_cmd
    )

    # ======================================================
    # Begin COMMAND INSIDE DOCKER
    # ======================================================

    # Send command to Docker shell
    child.sendline(
        performance_cmd
    )

    print(
        "\n[Wrapper] Performance command sent "
        "to Docker."
    )

    # ======================================================
    # FIND NEW PERFORMANCE LOG
    # ======================================================

    log_path = find_new_mlperf_log(
        old_log_snapshot,
        timeout=3000
    )

    if log_path is None:

        print(
            "\nERROR: Could not find the new MLPerf "
            "performance log."
        )

        print(
            "\nThe MLPerf process may still be running."
        )

        print(
            "You can check with:"
        )

        print(
            "ps aux | grep -E "
            "'mlcr|mlperf|loadgen' | grep -v grep"
        )

        exit_docker(
            child
        )

        monitor.stop()
        monitor_thread.join()

        sys.exit(1)

    # ======================================================
    # Begin WATCHER
    # ======================================================

    print(
        "\n[Wrapper] Starting MLPerf log watcher..."
    )

    watcher = MLPerfLogWatcher(
        monitor,
        log_path
    )

    # ------------------------------------------------------

    # pexpect has already started the MLPerf command.
    #
    # We therefore use the time immediately before the
    # performance command was sent as the process reference.
    # ------------------------------------------------------

    watcher.process_start_time = time.time()

    watcher_thread = threading.Thread(
        target=watcher.run,
        daemon=True
    )

    watcher_thread.start()

    print(
        "\n[Wrapper] MLPerf log watcher started."
    )

    # ======================================================
    # WAIT FOR BENCHMARK START
    # ======================================================

    print(
        "\n[Wrapper] Waiting for MLPerf LoadGen "
        "benchmark start..."
    )

    start_wait = time.time()

    while not watcher.benchmark_started:

        # --------------------------------------------------
        # Timeout protection
        # --------------------------------------------------

        if time.time() - start_wait > 300:

            print(
                "\nERROR: Timeout waiting for "
                "MLPerf benchmark start."
            )

            break

        # --------------------------------------------------
        # NOT utilising child.isalive() here.
        #
        # Docker shell stays alive while mlcr is running.
        # --------------------------------------------------

        time.sleep(
            0.2
        )

    # ======================================================
    # BENCHMARK Began
    # ======================================================

    if watcher.benchmark_started:

        print(
            "\n[Wrapper] MLPerf benchmark is running."
        )

        print(
            f"[Wrapper] benchmark_start = "
            f"{watcher.benchmark_start}"
        )

    # ======================================================
    # WAIT FOR BENCHMARK end
    # ======================================================

    print(
        "\n[Wrapper] Waiting for MLPerf LoadGen "
        "benchmark to finish..."
    )

    finish_wait = time.time()

    while not watcher.benchmark_finished:

        if time.time() - finish_wait > 1800:

            print(
                "\nERROR: Timeout waiting for "
                "MLPerf benchmark completion."
            )

            break

        time.sleep(
            0.2
        )

    # =====================================
    # BENCHMARK ended
    # =======================

    if watcher.benchmark_finished:

        print(
            "\n[Wrapper] MLPerf benchmark finished."
        )

        print(
            f"[Wrapper] benchmark_end = "
            f"{watcher.benchmark_end}"
        )

        if (
            watcher.benchmark_start is not None
            and
            watcher.benchmark_end is not None
        ):

            print(
                f"[Wrapper] benchmark duration = "
                f"{watcher.benchmark_end - watcher.benchmark_start:.6f} s"
            )

    else:

        print(
            "\nWARNING: MLPerf benchmark completion "
            "was not detected."
        )

    # ======================================================
    # WAIT FOR PERFORMANCE COMMAND TO RETURN
    # ======================================================

    wait_for_shell_prompt(
        child
    )

    # ======================================================
    # STOP WATCHER
    # ======================================================

    watcher.stop()

    watcher_thread.join(
        timeout=3
    )

    # ======================================================
    # SAVE TIMESTAMPS
    # ======================================================

    benchmark_start = (
        watcher.benchmark_start
    )

    benchmark_end = (
        watcher.benchmark_end
    )

    # ======================================================
    # EXIT DOCKER
    # ======================================================

    exit_docker(
        child
    )

    # ======================================================
    # COOLDOWN
    # ======================================================

    monitor.set_state(
        "cooldown"
    )

    print(
        "\nCool-down measurement..."
    )

    time.sleep(
        args.cooldown
    )

    # ======================================================
    # STOP MONITOR
    # ======================================================

    monitor.stop()

    monitor_thread.join()

    # ======================================================
    # CHECK TIMESTAMPS
    # ======================================================

    print(
        "\n"
        + "=" * 60
    )

    print(
        "MLPerf synchronization result"
    )

    print(
        "=" * 60
    )

    print(
        f"benchmark_start = "
        f"{benchmark_start}"
    )

    print(
        f"benchmark_end   = "
        f"{benchmark_end}"
    )

    if (
        benchmark_start is None
        or
        benchmark_end is None
    ):

        print(
            "\nERROR: Benchmark timestamps "
            "are missing."
        )

        print(
            "CSV/JSON export was NOT performed."
        )

        sys.exit(1)

    # ======================================================
    # EXPORT
    # ======================================================

    exporter = Exporter(
        csv_file=args.csv,
        json_file=args.json
    )

    exporter.save(
        monitor.samples,
        benchmark_start,
        benchmark_end
    )

    # ======================================================
    # FINAL OUTPUT
    # ======================================================

    print()

    print(
        "=" * 60
    )

    print(
        "Finished"
    )

    print(
        "=" * 60
    )

    print(
        "Return code : 0"
    )

    print(
        f"Samples     : "
        f"{len(monitor.samples)}"
    )

    print(
        f"CSV         : "
        f"{args.csv}"
    )

    print(
        f"JSON        : "
        f"{args.json}"
    )

    print(
        f"Benchmark duration : "
        f"{benchmark_end - benchmark_start:.6f} s"
    )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()
