"""
Instruction-Rate Throttle Engine

Regulates emulation speed so that the apparent instruction throughput
matches the Raspberry Pi 4's Cortex-A72 running at 1.5 GHz.

This is NOT cycle-accurate — it cannot model pipeline stalls, cache
misses, or branch prediction.  Instead, it ensures that N instructions
take the same wall-clock time they would take on a real 1.5 GHz core,
averaged over each execution batch.

Usage:
    throttle = ThrottleEngine(target_hz=1_500_000_000)
    
    while running:
        throttle.pre_batch()
        uc.emu_start(..., count=throttle.batch_size)
        throttle.post_batch()
"""

import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ThrottleStats:
    """Rolling statistics for the throttle engine."""
    total_instructions: int = 0
    total_wall_ns: int = 0
    total_sleep_ns: int = 0
    batches_executed: int = 0
    batches_throttled: int = 0
    current_mips: float = 0.0

    @property
    def avg_mips(self) -> float:
        if self.total_wall_ns == 0:
            return 0.0
        return (self.total_instructions / (self.total_wall_ns / 1e9)) / 1e6

    @property
    def throttle_ratio(self) -> float:
        """Fraction of time spent sleeping (0.0 = fully loaded, 1.0 = fully idle)."""
        if self.total_wall_ns == 0:
            return 0.0
        return self.total_sleep_ns / self.total_wall_ns


class ThrottleEngine:
    """Controls instruction execution rate to approximate real hardware speed.

    Args:
        target_hz:   Target instruction throughput in Hz (default 1.5 GHz).
        batch_size:  Instructions per execution batch (default 100,000).
        enabled:     If False, runs at maximum emulation speed.
    """

    def __init__(
        self,
        target_hz: int = 1_500_000_000,
        batch_size: int = 100_000,
        enabled: bool = True,
    ):
        self.target_hz = target_hz
        self.batch_size = batch_size
        self.enabled = enabled
        self.stats = ThrottleStats()

        # Pre-compute the target time per batch in nanoseconds
        self._target_batch_ns = int((batch_size / target_hz) * 1e9)

        # Timestamp captured by pre_batch()
        self._batch_start_ns: int = 0

        logger.info(
            "Throttle: target=%d Hz, batch=%d insns, "
            "target_batch_time=%.3f µs, enabled=%s",
            target_hz,
            batch_size,
            self._target_batch_ns / 1000,
            enabled,
        )

    def pre_batch(self):
        """Call immediately before starting an instruction batch."""
        self._batch_start_ns = time.perf_counter_ns()

    def post_batch(self, actual_insns: int = 0):
        """Call immediately after an instruction batch completes.

        Args:
            actual_insns: Actual number of instructions executed in this
                         batch (may differ from batch_size if execution
                         stopped early). If 0, assumes batch_size.
        """
        now = time.perf_counter_ns()
        elapsed_ns = now - self._batch_start_ns
        insns = actual_insns if actual_insns > 0 else self.batch_size

        # Update stats
        self.stats.total_instructions += insns
        self.stats.batches_executed += 1

        if elapsed_ns > 0:
            self.stats.current_mips = (insns / (elapsed_ns / 1e9)) / 1e6

        if not self.enabled:
            self.stats.total_wall_ns += elapsed_ns
            return

        # Calculate how long this batch *should* have taken
        target_ns = int((insns / self.target_hz) * 1e9)

        if elapsed_ns < target_ns:
            # We're running faster than real hardware — sleep the difference
            sleep_ns = target_ns - elapsed_ns
            if sleep_ns > 1_000:  # Only sleep if > 1µs (below that, spin)
                time.sleep(sleep_ns / 1e9)
                self.stats.total_sleep_ns += sleep_ns
                self.stats.batches_throttled += 1

        self.stats.total_wall_ns += max(elapsed_ns, target_ns)

    def set_speed(self, target_hz: int):
        """Change the target speed dynamically."""
        self.target_hz = target_hz
        self._target_batch_ns = int((self.batch_size / target_hz) * 1e9)
        logger.info("Throttle: speed changed to %d Hz", target_hz)

    def set_batch_size(self, batch_size: int):
        """Change the batch size dynamically."""
        self.batch_size = batch_size
        self._target_batch_ns = int((batch_size / self.target_hz) * 1e9)

    def get_summary(self) -> dict:
        """Return a summary of throttle performance."""
        return {
            "target_mhz": self.target_hz / 1e6,
            "current_mips": round(self.stats.current_mips, 1),
            "avg_mips": round(self.stats.avg_mips, 1),
            "total_instructions": self.stats.total_instructions,
            "batches": self.stats.batches_executed,
            "throttled_batches": self.stats.batches_throttled,
            "throttle_ratio": round(self.stats.throttle_ratio, 3),
            "enabled": self.enabled,
        }

    def __repr__(self):
        return (
            f"<ThrottleEngine target={self.target_hz/1e6:.0f} MHz "
            f"batch={self.batch_size} "
            f"current={self.stats.current_mips:.1f} MIPS>"
        )
