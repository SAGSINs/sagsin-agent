import os
import psutil
import subprocess
from typing import Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re
import subprocess
import time

executor = ThreadPoolExecutor()

def get_cpu_load(interval: float = 0.1) -> float:
    return psutil.cpu_percent(interval=interval)

def get_system_jitter(samples: int = 2, delay: float = 0.01) -> float:
    try:
        HOST_NAME = os.getenv("HOST_NAME", "unknown")
        if HOST_NAME == "unknown":
            PING_VALUE = "8.8.8.8"
        else:
            PING_VALUE = '192.168.100.10'
        cmd = ["ping", "-c", str(samples), "-i", str(delay), "-q", PING_VALUE]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        for line in output.splitlines():
            if "rtt" in line or "round-trip" in line:
                match = re.search(r"([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)", line)
                if match:
                    jitter_ms = float(match.group(4)) 
                    return round(jitter_ms, 3)
    except Exception as e:
        print(f"[WARN] Error in get_system_jitter: {e}")
        return 0.0
    return 0.0


def get_queue_length() -> int:
    try:
        interfaces = psutil.net_if_stats()
        active_iface = next((iface for iface, info in interfaces.items() if info.isup), None)
        if not active_iface:
            return 0

        result = subprocess.run(
            ["tc", "-s", "qdisc", "show", "dev", active_iface],
            capture_output=True,
            text=True
        )
        output = result.stdout

        match = re.search(r"backlog\s+(\d+)b\s+(\d+)p", output)
        if match:
            bytes_in_queue = int(match.group(1))
            packets_in_queue = int(match.group(2))
            return packets_in_queue

        return 0

    except Exception as e:
        print(f"[WARN] Error in get_queue_length: {e}")
        return 0

def get_throughput_mbps(interval: float = 0.1) -> float:
    counters1 = psutil.net_io_counters()
    bytes1 = counters1.bytes_sent + counters1.bytes_recv
    time.sleep(interval)
    counters2 = psutil.net_io_counters()
    bytes2 = counters2.bytes_sent + counters2.bytes_recv

    delta_bytes = bytes2 - bytes1
    mbps = (delta_bytes * 8) / (interval * 1_000_000) 
    return round(mbps, 3)

async def collect_node_metrics() -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    results = await asyncio.gather(
        loop.run_in_executor(executor, get_cpu_load, 0.1),
        loop.run_in_executor(executor, get_system_jitter),
        loop.run_in_executor(executor, get_queue_length),
        loop.run_in_executor(executor, get_throughput_mbps, 0.1),
    )
    cpu, jitter, queue, throughput = results
    return {
        "cpu_load": cpu,
        "jitter_ms": jitter,
        "queue_len": queue,
        "throughput_mbps": throughput,
    }