import os
import psutil
from typing import Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import random
import subprocess
import re
from .utils import (
    get_node_type,
    get_weather_condition,
    get_weather_impact,
    get_jitter_range,
    get_queue_capacity,
    calculate_queue_utilization
)

executor = ThreadPoolExecutor()

def get_cpu_load(interval: float = 0.1) -> float:
    return psutil.cpu_percent(interval=interval)

def get_system_jitter(samples: int = 2, delay: float = 0.01) -> float:
    """
    Hybrid approach: Measure real jitter, then adjust based on node type and weather
    """
    try:
        hostname = os.getenv("HOST_NAME", "unknown")
        node_type = get_node_type(hostname)
        weather = get_weather_condition(hostname)
        weather_impact = get_weather_impact(weather)
        
        # Try to measure real jitter first
        measured_jitter = None
        try:
            if hostname == "unknown":
                PING_VALUE = "8.8.8.8"
            else:
                PING_VALUE = '192.168.100.10'
            cmd = ["ping", "-c", str(samples), "-i", str(delay), "-q", PING_VALUE]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=2)
            for line in output.splitlines():
                if "rtt" in line or "round-trip" in line:
                    match = re.search(r"([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)", line)
                    if match:
                        measured_jitter = float(match.group(4))
                        break
        except:
            pass
        
        # If real measurement available, use it as base and adjust
        if measured_jitter is not None and measured_jitter > 0:
            # Adjust real measurement based on node type expectations
            jitter_min, jitter_max = get_jitter_range(node_type)
            expected_avg = (jitter_min + jitter_max) / 2
            
            # Blend: 70% real measurement, 30% expected value
            base_jitter = measured_jitter * 0.7 + expected_avg * 0.3
        else:
            # Fallback to simulation if measurement fails
            jitter_min, jitter_max = get_jitter_range(node_type)
            base_jitter = random.uniform(jitter_min, jitter_max)
        
        # Apply weather impact
        total_jitter = base_jitter * weather_impact["jitter"]
        return round(total_jitter, 3)
        
    except Exception as e:
        print(f"[WARN] Error in get_system_jitter: {e}")
        return round(random.uniform(2, 10), 3)


def get_queue_length() -> int:
    """
    Hybrid approach: Try to measure real queue, fallback to realistic simulation
    """
    try:
        hostname = os.getenv("HOST_NAME", "unknown")
        node_type = get_node_type(hostname)
        cpu_percent = get_cpu_load(interval=0.05)
        
        # Try to measure real queue length first
        real_queue = None
        try:
            interfaces = psutil.net_if_stats()
            active_iface = next((iface for iface, info in interfaces.items() if info.isup), None)
            if active_iface:
                result = subprocess.run(
                    ["tc", "-s", "qdisc", "show", "dev", active_iface],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                match = re.search(r"backlog\s+(\d+)b\s+(\d+)p", result.stdout)
                if match:
                    real_queue = int(match.group(2))
        except:
            pass
        
        # Get capacity expectations from config
        min_queue, max_queue = get_queue_capacity(node_type)
        
        # If real measurement available, use it but cap within node type range
        if real_queue is not None:
            # Real queue might be outside expected range, so normalize it
            queue_length = max(min_queue, min(real_queue, max_queue))
        else:
            # Fallback to simulation based on CPU load
            utilization = calculate_queue_utilization(cpu_percent)
            queue_length = int((min_queue + (max_queue - min_queue) * utilization))
        
        return queue_length
        
    except Exception as e:
        print(f"[WARN] Error in get_queue_length: {e}")
        return random.randint(0, 50)

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