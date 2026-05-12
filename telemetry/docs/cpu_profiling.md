# Telemetry CPU Profiling

Telemetry supports CPU profiling over specific intervals of interest during a benchmark run (e.g., during navigation, interactions, or the entire story run). This is currently supported on Linux, Android, and ChromeOS.

## Basic Usage

To enable CPU profiling, you need to specify at least the period(s) you want to profile and the target process.

```bash
./tools/perf/run_benchmark <benchmark_name> \
    --interval-profiling-period=<period> \
    --interval-profiling-target=<target>
```

### Profiling Periods (`--interval-profiling-period`)
You can specify one or more of the following:
*   `navigation`: Profiles during page navigation.
*   `interactions`: Profiles during user interactions (e.g., scrolling, clicking).
*   `story_run`: Profiles the entire duration of the story.

(see telemetry/telemetry/internal/browser/browser_options.py for the full list)

### Profiling Targets (`--interval-profiling-target`)
The target format is generally `PROCESS_NAME[:THREAD_NAME]`.

*   **Linux:**
    *   `renderer:main`: Profiles the main thread of the renderer process (default).
    *   `gpu`: Profiles the GPU process.
*   **Android:**
    *   Supports various processes and threads (e.g., `browser`, `renderer:main`, `gpu`).
*   **ChromeOS:**
    *   `system_wide`: Profiles the entire system.

## Platform Specifics

### Linux
Linux profiling uses the system `perf` tool (expected at `/usr/bin/perf`).
*   **Requirements:** You may need to have `perf` installed and permissions configured to allow profiling (e.g., `/proc/sys/kernel/perf_event_paranoid`).
*   **Note:** Using CPU profiling on Linux automatically adds `--no-sandbox` to the browser arguments.

Example:
```bash
./tools/perf/run_benchmark rasterize_and_record_micro.top_25 \
    --browser=release \
    --story-filter=yahoosports.html \
    --interval-profiling-period=story_run \
    --interval-profiling-target=gpu
```

### Android
Android profiling uses `simpleperf`, which Telemetry automatically installs on the device.
*   **Requirements:** Requires a "userdebug" build of Android and `adb root` access.
*   **Frequency:** You can control the sampling frequency with `--interval-profiling-frequency` (default is 1000 Hz).

### ChromeOS
ChromeOS supports system-wide profiling using `perf`.
*   **Requirements:** You must provide additional profiler options via `--interval-profiler-options`.

Example:
```bash
./tools/perf/run_benchmark <benchmark> \
    --interval-profiling-period=story_run \
    --interval-profiling-target=system_wide \
    --interval-profiler-options="record -g"
```

## Results
Profile data is collected as artifacts and can be found in the output directory:
*   **Linux:** `perf-*.perf.data` files.
*   **Android:** `simpleperf-*.perf.data` files.
*   **ChromeOS:** `perf-*.perf.data` files.

These files can be analyzed using standard tools like `perf report` (for Linux/ChromeOS) or `simpleperf report` (for Android).
