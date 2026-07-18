import os
import signal
import subprocess
import sys
import time


SHUTDOWN_TIMEOUT_SECONDS = 20


def build_processes() -> list[tuple[str, list[str]]]:
    port = os.getenv("PORT", "8000")
    return [
        ("worker", [sys.executable, "worker.py"]),
        (
            "api",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                port,
            ],
        ),
    ]


def start_process(name: str, command: list[str]) -> subprocess.Popen:
    print(f"Starting {name}: {' '.join(command)}", flush=True)
    try:
        return subprocess.Popen(command)
    except Exception as exc:
        print(f"Failed to start {name}: {exc}", file=sys.stderr, flush=True)
        raise


def terminate_process(process: subprocess.Popen, name: str) -> None:
    if process.poll() is not None:
        return

    print(f"Stopping {name}...", flush=True)
    try:
        process.terminate()
        process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(f"{name} did not stop in time; killing it.", file=sys.stderr, flush=True)
        process.kill()
        process.wait()


def shutdown(processes: dict[str, subprocess.Popen]) -> None:
    for name, process in processes.items():
        terminate_process(process, name)


def main() -> int:
    processes: dict[str, subprocess.Popen] = {}
    shutting_down = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print(f"Received signal {signum}; shutting down WebScope processes.", flush=True)
        shutdown(processes)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        for name, command in build_processes():
            processes[name] = start_process(name, command)

        while not shutting_down:
            for name, process in processes.items():
                return_code = process.poll()
                if return_code is not None:
                    print(
                        f"{name} exited with code {return_code}; stopping remaining processes.",
                        file=sys.stderr,
                        flush=True,
                    )
                    shutdown(processes)
                    return return_code
            time.sleep(1)
    except Exception:
        shutdown(processes)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
