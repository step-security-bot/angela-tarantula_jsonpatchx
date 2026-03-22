from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

DEMOS: dict[str, tuple[str, str, int]] = {
    "1": ("Support desk corrections", "examples.fastapi.demo1:app", 8000),
    "2": ("Player and guild progression", "examples.fastapi.demo2:app", 8001),
    "3": ("Control plane configs", "examples.fastapi.demo3:app", 8002),
    "4": ("Spellbook rune pointers", "examples.fastapi.demo4:app", 8003),
    "5": ("Explicit custom backend ops", "examples.fastapi.demo5:app", 8004),
    "6": ("Generic P backend ops", "examples.fastapi.demo6:app", 8005),
}


def run_demo(choice: str) -> None:
    name, app_path, port = DEMOS[choice]
    print(f"\n--- Launching {name} ---")

    cmd = [sys.executable, "-m", "uvicorn", app_path, "--port", str(port), "--reload"]
    proc = subprocess.Popen(cmd, start_new_session=True)
    print(f"Swagger: http://127.0.0.1:{port}/docs")

    print("\nPress Ctrl+C to stop the server...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
        print("\nServer stopped.")


def main() -> None:
    print("Available demos:")
    for key, (label, _, port) in DEMOS.items():
        print(f"  {key}) {label} (port {port})")

    choice = input("\nSelect a demo (1-6): ").strip()
    if choice not in DEMOS:
        print("Invalid choice.")
        return
    run_demo(choice)


if __name__ == "__main__":
    main()
