import asyncio
import random
import re
import os
import math
from .utils import (
    get_node_type,
    get_weather_condition,
    get_weather_impact,
    get_link_delay_range,
    get_jitter_ratio,
    get_base_loss_rate,
    get_bandwidth_range,
    get_propagation_delay_factor,
    get_node_info,
    haversine_distance
)

PING_REGEX = re.compile(r"= ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms")

def calculate_realistic_link_metrics(src_hostname: str, dst_hostname: str, distance_km: float) -> dict:
    src_type = get_node_type(src_hostname)
    dst_type = get_node_type(dst_hostname)
    weather = get_weather_condition(src_hostname)
    weather_impact = get_weather_impact(weather)
    
    delay_min, delay_max = get_link_delay_range(src_type, dst_type)
    base_delay = random.uniform(delay_min, delay_max)
    
    prop_delay_factor = get_propagation_delay_factor(src_type, dst_type)
    prop_delay = distance_km * prop_delay_factor
    
    delay_ms = (base_delay + prop_delay) * weather_impact["delay"]
    
    # Calculate jitter as percentage of delay
    jitter_ratio = max(get_jitter_ratio(src_type), get_jitter_ratio(dst_type))
    jitter_ms = delay_ms * jitter_ratio * weather_impact["jitter"]
    
    # Calculate loss rate with weather impact
    src_loss_min, src_loss_max = get_base_loss_rate(src_type)
    dst_loss_min, dst_loss_max = get_base_loss_rate(dst_type)
    base_loss = max(random.uniform(src_loss_min, src_loss_max), 
                    random.uniform(dst_loss_min, dst_loss_max))
    loss_rate = min(base_loss * weather_impact["loss"], 0.10)  # Cap at 10%
    
    # Calculate bandwidth with weather impact
    bw_min, bw_max = get_bandwidth_range(src_type, dst_type)
    bandwidth_mbps = random.uniform(bw_min, bw_max) * weather_impact["bandwidth"]
    
    return {
        "delay_ms": round(delay_ms, 2),
        "jitter_ms": round(jitter_ms, 2),
        "loss_rate": round(loss_rate, 4),
        "bandwidth_mbps": round(bandwidth_mbps, 2)
    }

async def ping_neighbor(neighbor_hostname: str) -> dict:
    try:
        current_hostname = os.getenv("HOST_NAME", "unknown")
        
        # Get current node GPS from topology.json
        current_node_info = get_node_info(current_hostname)
        current_lat = current_node_info["lat"]
        current_lng = current_node_info["lng"]
        
        # Get neighbor GPS from topology.json
        neighbor_node_info = get_node_info(neighbor_hostname)
        neighbor_lat = neighbor_node_info["lat"]
        neighbor_lng = neighbor_node_info["lng"]
        
        args = ["ping", "-c", "3", "-W", "2", neighbor_hostname] if os.name != "nt" else ["ping", "-n", "3", "-w", "2000", neighbor_hostname]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        measured_delay = None
        measured_jitter = None
        measured_loss = 0.0
        available = False
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=4)
            output = stdout.decode()
            
            if proc.returncode == 0:
                available = True
                
                # Extract RTT stats (min/avg/max/mdev)
                match = PING_REGEX.search(output)
                if match:
                    measured_delay = float(match.group(2))  # avg
                    measured_jitter = float(match.group(4))  # mdev (standard deviation)
                
                # Extract packet loss
                loss_match = re.search(r"(\d+)% packet loss", output)
                if loss_match:
                    measured_loss = float(loss_match.group(1)) / 100.0
                    
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            available = False
        
        if not available:
            return {
                "neighbor_id": neighbor_hostname,
                "delay_ms": 0.0,
                "jitter_ms": 0.0,
                "loss_rate": 1.0,
                "bandwidth_mbps": 0.0,
                "available": False,
                "queue_length": 0
            }
        
        # Calculate REAL distance using GPS coordinates from topology.json
        distance_km = haversine_distance(current_lat, current_lng, neighbor_lat, neighbor_lng)
        
        # Calculate expected metrics based on real distance
        expected_metrics = calculate_realistic_link_metrics(current_hostname, neighbor_hostname, distance_km)
        
        # Hybrid approach: Blend real measurements with expected values
        if measured_delay is not None and measured_delay > 0:
            # Use 60% real measurement + 40% expected (physics-based)
            # This ensures realistic values while incorporating actual network conditions
            final_delay = measured_delay * 0.6 + expected_metrics["delay_ms"] * 0.4
        else:
            final_delay = expected_metrics["delay_ms"]
        
        if measured_jitter is not None and measured_jitter > 0:
            # Blend real jitter with expected jitter ratio
            final_jitter = measured_jitter * 0.6 + expected_metrics["jitter_ms"] * 0.4
        else:
            final_jitter = expected_metrics["jitter_ms"]
        
        # Loss rate: use real if available, otherwise expected
        if measured_loss > 0:
            final_loss = measured_loss * 0.7 + expected_metrics["loss_rate"] * 0.3
        else:
            final_loss = expected_metrics["loss_rate"]
        
        # Bandwidth: mostly from expected (hard to measure accurately with ping)
        final_bandwidth = expected_metrics["bandwidth_mbps"]
        
        # Queue length correlates with loss and delay
        base_queue = 10
        queue_length = int(base_queue + final_loss * 500 + (final_delay / 10) + random.randint(0, 30))
        queue_length = max(0, min(queue_length, 200))
        
        return {
            "neighbor_id": neighbor_hostname,
            "delay_ms": round(final_delay, 2),
            "jitter_ms": round(final_jitter, 2),
            "loss_rate": round(final_loss, 4),
            "bandwidth_mbps": round(final_bandwidth, 2),
            "available": True,
            "queue_length": queue_length
        }
        
    except Exception as e:
        print(f"Error measuring metrics to {neighbor_hostname}: {e}")
        return {
            "neighbor_id": neighbor_hostname,
            "delay_ms": 0.0,
            "jitter_ms": 0.0,
            "loss_rate": 1.0,
            "bandwidth_mbps": 0.0,
            "available": False,
            "queue_length": 0
        }

async def measure_links(neighbors: list) -> list:
    tasks = [ping_neighbor(n) for n in neighbors]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    links = []
    for i, result in enumerate(results):
        if isinstance(result, dict):
            links.append(result)
        else:
            links.append({
                "neighbor_id": neighbors[i],
                "delay_ms": 0.0,
                "jitter_ms": 0.0,
                "loss_rate": 1.0,
                "bandwidth_mbps": 0.0,
                "available": False,
                "queue_length": 0
            })
    return links
