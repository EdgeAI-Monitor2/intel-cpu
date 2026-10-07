#!/usr/bin/env python3
import os
import json
import time
class MLPerfLogWatcher:
    def __init__(self, monitor, log_path):
        self.monitor = monitor
        self.log_path = log_path
        self.running = False
        self.benchmark_started = False
        self.benchmark_finished = False
        self.benchmark_start = None
        self.benchmark_end = None
        self.process_start_time = None
# ======================================
    # STOP
    # ==================================================

    def stop(self):

        self.running = False

    # ======================================================
    # RUN
    # ======================================================

    def run(self):

        self.running = True

        print(
            f"[Watcher] Opening MLPerf log:\n"
            f"{self.log_path}"
        )

        # --------------------------------------------------
        # Wait for file
        # --------------------------------------------------

        while (
            self.running
            and
            not os.path.exists(self.log_path)
        ):

            time.sleep(0.2)

        if not self.running:
            return

        # --------------------------------------------------
        # Open MLPerf log
        # --------------------------------------------------

        try:

            with open(
                self.log_path,
                "r",
                buffering=1
            ) as f:

                # Start from beginning of file
                f.seek(0)

                while self.running:

                    line = f.readline()

           # --------------------------------------------------
               # MLPerf is still writing the file.
                  #
                   # NOT exiting here.
                    # Wait for more data.
                    # --------------------------------------------------

                    if not line:

                        time.sleep(0.1)

                        continue

                    line = line.strip()

                    # ==================================================
                    # Ignore non-MLLOG lines
                    # ==================================================

                    if not line.startswith(
                        ":::MLLOG "
                    ):

                        continue

                    # ==================================================
                    # Parse MLLOG JSON
                    # ==================================================

                    try:

                        json_text = line[
                            len(":::MLLOG "):
                        ]

                        record = json.loads(
                            json_text
                        )

                    except Exception:

                        continue

                    key = record.get(
                        "key",
                        ""
                    )

                    value = record.get(
                        "value",
                        ""
                    )

                    time_ms = record.get(
                        "time_ms"
                    )

                    # ==================================================
                    #The beginning OF PERFORMANCE
                    # ==================================================

                    if (
                        key == "generic_message"
                        and
                        value == "Starting performance mode"
                    ):

                        if not self.benchmark_started:

                            self.benchmark_started = True

                            print(
                                "\n[Watcher] =================================="
                            )

                            print(
                                "[Watcher] Benchmark START detected"
                            )

                            # --------------------------------------------------
                            # LoadGen timestamp
                            # --------------------------------------------------

                            if time_ms is not None:

                                loadgen_time = (
                                    float(time_ms) / 1000.0
                                )

                                print(
                                    f"[Watcher] LoadGen time = "
                                    f"{loadgen_time:.6f} s"
                                )

                            else:

                                loadgen_time = 0.0

                                print(
                                    "[Watcher] WARNING: "
                                    "No LoadGen time found."
                                )

                            # --------------------------------------------------
                            # Host timestamp
                            # --------------------------------------------------

                            if self.process_start_time is not None:

                                self.benchmark_start = (
                                    self.process_start_time
                                    +
                                    loadgen_time
                                )

                            else:

                                # Fallback
                                self.benchmark_start = time.time()

                            print(
                                f"[Watcher] Host time = "
                                f"{self.benchmark_start}"
                            )

                            self.monitor.set_state(
                                "benchmark"
                            )

                            print(
                                "[Watcher] State = benchmark"
                            )

                            print(
                                "[Watcher] =================================="
                            )

                    # ==================================================
                    # END OF PERFORMANCE
                    # ==================================================

                    if (
                        key == "generic_message"
                        and
                        isinstance(value, str)
                        and
                        value.startswith(
                            "Ending naturally"
                        )
                    ):

                        if (
                            self.benchmark_started
                            and
                            not self.benchmark_finished
                        ):

                            self.benchmark_finished = True

                            print(
                                "\n[Watcher] =================================="
                            )

                            print(
                                "[Watcher] Benchmark FINISH detected"
                            )
                            # --------------------------------------------------
                            # LoadGen timestamp
                            # --------------------------------------------------
                            if time_ms is not None:
                                loadgen_time = (
                                    float(time_ms) / 1000.0
                                )

                                print(
                                    f"[Watcher] LoadGen end time = "
                                    f"{loadgen_time:.6f} s"
                                )

                            else:

                                loadgen_time = 0.0

                                print(
                                    "[Watcher] WARNING: "
                                    "No LoadGen end time found."
                                )

                            # --------------------------------------------------
                            # Host timestamp
                            # --------------------------------------------------

                            if self.process_start_time is not None:

                                self.benchmark_end = (
                                    self.process_start_time
                                    +
                                    loadgen_time
                                )

                            else:

                                self.benchmark_end = time.time()

                            print(
                                f"[Watcher] Host end time = "
                                f"{self.benchmark_end}"
                            )

                            self.monitor.set_state(
                                "postprocess"
                            )

                            print(
                                "[Watcher] State = postprocess"
                            )

                            print(
                                "[Watcher] =================================="
                            )

                            # --------------------------------------------------
                            # It is possible to stop watching once the benchmark
                            # has actually ended.
                            # --------------------------------------------------

                            self.running = False

                            break

        except Exception as e:

            print(
                "\n[Watcher] ERROR while reading MLPerf log:"
            )

            print(
                repr(e)
            )

            self.running = False
