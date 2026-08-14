import threading
import time
from collections import defaultdict
from contextlib import contextmanager


class Timings:
    """Accumulates named (count, total_seconds) buckets, thread-safe within a process."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = defaultdict(lambda: [0, 0.0])

    @contextmanager
    def timed(self, label):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            with self._lock:
                entry = self._data[label]
                entry[0] += 1
                entry[1] += elapsed

    def snapshot(self):
        """Returns a plain, picklable dict so results can cross process boundaries."""
        with self._lock:
            return {label: (count, total) for label, (count, total) in self._data.items()}

    @staticmethod
    def merge_snapshots(*snapshots):
        merged = defaultdict(lambda: [0, 0.0])
        for snapshot in snapshots:
            for label, (count, total) in snapshot.items():
                entry = merged[label]
                entry[0] += count
                entry[1] += total
        return {label: (count, total) for label, (count, total) in merged.items()}

    @staticmethod
    def format_report(snapshot):
        if not snapshot:
            return "Timing breakdown: (no data)"
        lines = ["Timing breakdown:"]
        for label, (count, total) in sorted(snapshot.items(), key=lambda kv: kv[1][1], reverse=True):
            avg_ms = (total / count * 1000) if count else 0.0
            lines.append(f"  {label}: {total:.3f}s total, {count} calls, {avg_ms:.1f}ms avg")
        return "\n".join(lines)
