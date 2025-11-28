import subprocess
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PingResult:
    ip: str
    alive: bool
    avg_ms: float
    packet_loss: float
    jitter_ms: float



def probe_host(ip: str, count: int = 5, timeout: float = 2.0) -> PingResult:
    """
    Ping `ip` count times using system ping command.
    """
    try:
        # Use system ping command (more reliable in containers)
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', str(int(timeout * 1000)), ip],
            capture_output=True,
            text=True,
            timeout=timeout * count + 2
        )
        
        if result.returncode == 0:
            # Parse ping output
            output = result.stdout
            # Extract packet loss
            loss_match = re.search(r'(\d+)% packet loss', output)
            packet_loss = float(loss_match.group(1)) if loss_match else 100.0
            
            # Extract RTT stats
            rtt_match = re.search(r'min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', output)
            if rtt_match:
                min_rtt = float(rtt_match.group(1))
                avg_rtt = float(rtt_match.group(2))
                max_rtt = float(rtt_match.group(3))
                jitter = float(rtt_match.group(4))
                alive = packet_loss < 100.0
            else:
                avg_rtt = 0.0
                jitter = 0.0
                alive = False
        else:
            alive = False
            avg_rtt = 0.0
            packet_loss = 100.0
            jitter = 0.0
            
    except Exception as e:
        print(f"DEBUG: Ping error for {ip}: {e}")
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