import os
import time
from dataclasses import dataclass
from typing import Dict
from dotenv import load_dotenv
import schedule

from network.ping import PingResult, probe_host
from enum import Enum
import platform
import subprocess

load_dotenv()

GATEWAY_IP = os.getenv("GATEWAY_IP", "192.168.1.1")
REFERENCE_IP = os.getenv("REFERENCE_IP", "8.8.8.8")
TARGET_IP = os.getenv("TARGET_IP", "1.1.1.1")
_DEFAULT_TARGET_IP = os.getenv("TARGET_IP", "1.1.1.1")
PING_COUNT = 5
PING_TIMEOUT = 2.0


@dataclass
class MonitorSnapshot:
    timestamp: float
    gateway: PingResult
    reference: PingResult
    target: PingResult
    
class Diagnosis(Enum):
    LOCAL = "Local router issue"
    ISP = "ISP issue"
    TARGET_DOWN = "Target unreachable"
    ROUTING = "Routing issue"
    CONGESTION = "High latency / congestion"
    HEALTHY = "Healthy"


_last_snapshot: MonitorSnapshot | None = None


def run_cycle() -> None:
    global _last_snapshot
    
    # Read TARGET_IP dynamically each cycle
    target_ip = os.getenv("TARGET_IP", _DEFAULT_TARGET_IP)

    gateway = probe_host(GATEWAY_IP, count=PING_COUNT, timeout=PING_TIMEOUT)
    reference = probe_host(REFERENCE_IP, count=PING_COUNT, timeout=PING_TIMEOUT)
    target = probe_host(target_ip, count=PING_COUNT, timeout=PING_TIMEOUT)  # Use dynamic value

    _last_snapshot = MonitorSnapshot(
        timestamp=time.time(),
        gateway=gateway,
        reference=reference,
        target=target,
    )

    # Placeholder for logic layer (Step 4) – simply print now
    diagnosis = classify(_last_snapshot)
    print(format_snapshot(_last_snapshot))
    print(f"Diagnosis: {diagnosis.value}\n")

def format_snapshot(snapshot: MonitorSnapshot) -> str:
    def fmt(result: PingResult) -> str:
        status = "OK" if result.alive else "FAIL"
        return (
            f"{result.ip} [{status}] "
            f"{result.avg_ms:.1f}ms avg / "
            f"{result.jitter_ms:.1f}ms jitter / "
            f"{result.packet_loss:.0f}% loss"
        )

    return (
        f"Gateway:   {fmt(snapshot.gateway)}\n"
        f"Reference: {fmt(snapshot.reference)}\n"
        f"Target:    {fmt(snapshot.target)}\n"
    )

def classify(snapshot: MonitorSnapshot) -> Diagnosis:
    g = snapshot.gateway
    r = snapshot.reference
    t = snapshot.target

    if not g.alive:
        return Diagnosis.LOCAL
    if g.alive and not r.alive and not t.alive:
        return Diagnosis.ISP
    if g.alive and r.alive and not t.alive:
        return Diagnosis.TARGET_DOWN
    if g.alive and r.alive and t.alive:
        if r.avg_ms > 150 and t.avg_ms > 150:
            return Diagnosis.CONGESTION
        if r.avg_ms < 80 and t.avg_ms > 150:
            return Diagnosis.ROUTING
        return Diagnosis.HEALTHY
    return Diagnosis.HEALTHY

def start_monitor(interval_seconds: int = 30) -> None:
    schedule.every(interval_seconds).seconds.do(run_cycle)

    run_cycle()  # immediate first run
    while True:
        schedule.run_pending()
        time.sleep(1)

def traceroute(host: str, max_hops: int = 20) -> str:
    system = platform.system().lower()
    if system == "windows":
        cmd = ["tracert", "-h", str(max_hops), host]
    else:
        cmd = ["traceroute", "-m", str(max_hops), host]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return result.stdout or result.stderr or "Traceroute produced no output."
    except Exception as exc:
        return f"Traceroute failed: {exc}"

def latest_snapshot() -> MonitorSnapshot | None:
    return _last_snapshot