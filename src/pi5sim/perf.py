"""Pace user scripts to Raspberry Pi 5 CPU speed.

The host is benchmarked once; the user process is then duty-cycled with suspend/resume
so CPU-bound Python runs about as fast as on a Pi 5, and it is pinned to 4 cores.

Measure a real Pi 5 with `python -m pi5sim.perf` and put the score in PI5SIM_REF_SCORE.
"""
import os
import threading
import time

import psutil

from pi5sim import board

# shortcut: estimated CPython score for a Pi 5 @ 2.4 GHz (~1/3 of a modern desktop core);
# replace with a value measured on real hardware via PI5SIM_REF_SCORE.
PI5_REF_SCORE = 8.0e6
PERIOD = 0.05  # duty-cycle period in seconds
TREE_REFRESH = 1.0  # seconds between process-tree rescans


def bench(duration: float = 1.0) -> float:
    """Simple single-core CPython loop score (iterations / second)."""
    n = x = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration:
        for i in range(10000):
            x += i * i % 7
        n += 10000
    return n / (time.perf_counter() - t0)


def ref_score() -> float:
    return float(os.environ.get("PI5SIM_REF_SCORE", PI5_REF_SCORE))


def speed_ratio(host_score: float, pi_score: float | None = None) -> float:
    """Fraction of wall time the user process may run (1.0 = no throttling)."""
    return min(1.0, (pi_score or ref_score()) / host_score)


class Pacer:
    """Duty-cycles one process to `ratio` of its natural speed until it exits."""

    def __init__(self, pid: int, ratio: float):
        self.ratio = ratio
        self.proc = psutil.Process(pid)
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _tree(self):
        # A Windows venv python.exe is a launcher; the real interpreter is its child.
        try:
            return [self.proc] + self.proc.children(recursive=True)
        except psutil.Error:
            return []

    @staticmethod
    def _each(tree, method, *args):
        for p in tree:
            try:
                getattr(p, method)(*args)
            except (psutil.Error, AttributeError):
                pass  # exited, or cpu_affinity unavailable (macOS)

    def _refresh(self, cpus, pinned):
        """Rescan the process tree and pin new processes to 4 cores."""
        tree = self._tree()
        for p in tree:
            if p.pid not in pinned:
                pinned.add(p.pid)
                self._each([p], "cpu_affinity", cpus)
        return tree

    def _loop(self):
        run, pause = PERIOD * self.ratio, PERIOD * (1 - self.ratio)
        cpus = list(range(min(board.CORES, os.cpu_count() or 1)))
        pinned = set()
        next_scan, interval = 0.0, PERIOD
        try:
            while not self._stop.is_set() and self.proc.is_running():
                # Scanning the tree costs ~5 ms on Windows. Scan often at start (the venv launcher
                # spawns the real interpreter a moment later), then back off to once a second.
                if time.monotonic() >= next_scan:
                    tree = self._refresh(cpus, pinned)
                    next_scan = time.monotonic() + interval
                    interval = min(TREE_REFRESH, interval * 2)
                if pause <= 0:
                    self._stop.wait(0.5)
                    continue
                self._stop.wait(run)
                self._each(tree, "suspend")
                try:
                    self._stop.wait(pause)
                finally:
                    self._each(tree, "resume")
        except psutil.Error:
            pass


if __name__ == "__main__":
    s = bench(3.0)
    print(f"score: {s:.0f}")
    print(f"export PI5SIM_REF_SCORE={s:.0f}   # run this on a real Pi 5 to calibrate")
