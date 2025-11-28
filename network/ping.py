from dataclasses import dataclass
from typing import Optional

from icmplib import multiping
from icmplib.exceptions import ICMPLibError


@dataclass
class PingResult:
    ip: str
    alive: bool
    avg_ms: float
    packet_loss: float
    jitter_ms: float


def probe_host(ip: str, count: int = 5, timeout: float = 2.0) -> PingResult:
    """
    Ping `ip` count times and summarize reachability, latency, and jitter stats.
    """
    try:
        hosts = multiping(
            [ip],
            count=count,
            timeout=timeout,
            interval=0.2,
            privileged=False,  # keeps it usable without raw-socket perms
        )
        host = hosts[0]
        alive = host.is_alive
        avg_rtt = host.avg_rtt or 0.0
        packet_loss = host.packet_loss * 100.0
        jitter = (host.max_rtt - host.min_rtt) if host.packets_received else 0.0
    except ICMPLibError:
        alive = False
        avg_rtt = 0.0
        packet_loss = 100.0
        jitter = 0.0

    return PingResult(
        ip=ip,
        alive=alive,
        avg_ms=avg_rtt,
        packet_loss=packet_loss,
        jitter_ms=jitter,
    )