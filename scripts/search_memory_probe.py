"""Measure RSS peak/time of DataRepository.search() without psutil (ctypes)."""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from api.services.data import DataRepository  # noqa: E402

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.K32GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
    wintypes.DWORD,
]
_k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL


def _counters() -> PROCESS_MEMORY_COUNTERS:
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    _k32.K32GetProcessMemoryInfo(
        _k32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    return counters


def rss_bytes() -> int:
    return _counters().WorkingSetSize


def peak_rss_bytes() -> int:
    return _counters().PeakWorkingSetSize


def main() -> None:
    queries = sys.argv[1:] or ["zzz", "delhi", "WH-001", "critical"]
    repo = DataRepository()
    baseline = rss_bytes()
    peak = [baseline]
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            peak[0] = max(peak[0], rss_bytes())
            time.sleep(0.02)

    threading.Thread(target=sample, daemon=True).start()
    print(f"baseline RSS: {baseline / 1048576:.1f} MB")
    for q in queries:
        t0 = time.time()
        results = repo.search(q)
        print(
            f"search({q!r}): {time.time() - t0:.2f}s, "
            f"{len(results)} results, RSS {rss_bytes() / 1048576:.1f} MB"
        )
    stop.set()
    time.sleep(0.1)
    print(f"peak RSS during run: {max(peak[0], peak_rss_bytes()) / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
