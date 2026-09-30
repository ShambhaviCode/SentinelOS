"""Machine, runtime and network facts, read from the system at runtime.

Anything that cannot be read is reported as "Not detected"; nothing is assumed.
"""
from __future__ import annotations

import platform
import socket
import sys
import time
from typing import Any

NOT_DETECTED = "Not detected"
_net_cache: dict[str, Any] = {"t": 0.0, "value": None}


def processor_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or NOT_DETECTED


def machine_info() -> dict[str, Any]:
    info = {
        "processor": processor_name(),
        "os": f"{platform.system()} {platform.release()} (build {platform.version()})",
        "python": platform.python_version(),
        "python_arch": platform.machine() or NOT_DETECTED,   # ARM64 = native on Snapdragon; AMD64 = emulated x64
        "onnxruntime": NOT_DETECTED,
        "available_providers": [],
        "memory_rss_mb": None,
    }
    try:
        import onnxruntime as ort
        info["onnxruntime"] = ort.__version__
        info["available_providers"] = ort.get_available_providers()
    except Exception:
        pass
    info["memory_rss_mb"] = process_rss_mb()
    return info


def process_rss_mb() -> float | None:
    try:
        import psutil  # optional
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                return round(pmc.WorkingSetSize / 1e6, 1)
        except Exception:
            return None
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3, 1)  # peak, Linux KB
    except Exception:
        return None


def network_status(ttl: float = 10.0) -> str:
    """'online' if a TCP connection to a public resolver succeeds within 0.5 s, else 'offline'.

    This is a status probe for the UI only; the analysis path makes no network calls.
    """
    now = time.monotonic()
    if _net_cache["value"] is not None and now - _net_cache["t"] < ttl:
        return _net_cache["value"]
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=0.5):
            value = "online"
    except OSError:
        value = "offline"
    _net_cache.update(t=now, value=value)
    return value
