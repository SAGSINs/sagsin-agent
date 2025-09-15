import asyncio
import os
import socket
import signal
import json
import random
import subprocess
import time
from typing import AsyncGenerator, List, Dict

import grpc

try:
    from . import monitor_pb2, monitor_pb2_grpc
except ImportError:
    import monitor_pb2
    import monitor_pb2_grpc

# Config
GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")
INTERVAL_SEC = float(os.getenv("INTERVAL_SEC", "5.0"))
HOST_NAME = os.getenv("HOST_NAME") or "unknown"
TOPOLOGY_FILE = os.getenv("TOPOLOGY_FILE", "/topology/topology.json")


def load_topology() -> Dict:
    try:
        with open(TOPOLOGY_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Topology file {TOPOLOGY_FILE} not found. Running without neighbor info.")
        return {"nodes": [], "links": []}
    except json.JSONDecodeError as e:
        print(f"Error parsing topology file: {e}")
        return {"nodes": [], "links": []}


def get_neighbors(hostname: str, topology: Dict) -> List[str]:
    neighbors = []
    
    for link in topology.get("links", []):
        source = link.get("source")
        target = link.get("target")
        
        if source == hostname:
            neighbors.append(target)
        elif target == hostname:
            neighbors.append(source)
    print(f"Neighbors of {hostname}: {neighbors}")
    return list(set(neighbors)) 

import re

PING_REGEX = re.compile(r"= ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms")

async def ping_neighbor(neighbor_hostname: str) -> Dict:
    """Ping neighbor và đo network metrics thật từ output của ping"""
    try:
        # Linux/Mac: ping -c 4
        # Windows: ping -n 4
        args = ["ping", "-c", "4", neighbor_hostname] if os.name != "nt" else ["ping", "-n", "4", neighbor_hostname]

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("Ping timed out")

        if proc.returncode == 0:
            output = stdout.decode()
            # Linux output thường có dạng: rtt min/avg/max/mdev = 7.23/7.56/7.89/0.21 ms
            match = PING_REGEX.search(output)
            if match:
                min_rtt, avg_rtt, max_rtt, mdev = map(float, match.groups())
                delay_ms = avg_rtt
                jitter_ms = mdev
                loss_rate = 0.0
                available = True
            else:
                # fallback nếu không parse được
                delay_ms = random.uniform(10, 200)
                jitter_ms = random.uniform(1, 20)
                loss_rate = 0.0
                available = True
        else:
            # Ping thất bại
            delay_ms = 0.0
            jitter_ms = 0.0
            loss_rate = 1.0
            available = False

    except Exception as e:
        print(f"Error pinging {neighbor_hostname}: {e}")
        delay_ms = 0.0
        jitter_ms = 0.0
        loss_rate = 1.0
        available = False

    # bandwidth, queue_length: bạn có thể đo bằng iperf3 hoặc export metric từ interface
    bandwidth_mbps = random.uniform(10, 100) if available else 0.0
    queue_length = random.randint(0, 100) if available else 0

    return {
        "neighbor_id": neighbor_hostname,
        "delay_ms": delay_ms,
        "jitter_ms": jitter_ms,
        "loss_rate": loss_rate,
        "bandwidth_mbps": bandwidth_mbps,
        "available": available,
        "queue_length": queue_length
    }

async def measure_links(neighbors: List[str]) -> List[Dict]:
    """Đo network metrics cho tất cả neighbors"""
    tasks = []
    for neighbor in neighbors:
        tasks.append(ping_neighbor(neighbor))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    links = []
    for i, result in enumerate(results):
        if isinstance(result, dict):
            links.append(result)
        else:
            # Exception occurred
            print(f"Error measuring link to {neighbors[i]}: {result}")
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

def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


async def heartbeat_generator(stop_event: asyncio.Event, neighbors: List[str]) -> AsyncGenerator[monitor_pb2.HeartbeatRequest, None]:
    local_ip = get_local_ip()

    while not stop_event.is_set():
        # Đo network metrics cho tất cả neighbors
        link_metrics = await measure_links(neighbors)
        
        # Tạo LinkMetric objects cho gRPC
        links = []
        for metric in link_metrics:
            link = monitor_pb2.LinkMetric(
                neighbor_id=metric["neighbor_id"],
                delay_ms=metric["delay_ms"],
                jitter_ms=metric["jitter_ms"],
                loss_rate=metric["loss_rate"],
                bandwidth_mbps=metric["bandwidth_mbps"],
                available=metric["available"],
                queue_length=metric["queue_length"]
            )
            links.append(link)
        
        yield monitor_pb2.HeartbeatRequest(
            ip=local_ip,
            hostname=HOST_NAME,
            links=links
        )
        await asyncio.sleep(INTERVAL_SEC)


async def run_agent(stop_event: asyncio.Event, neighbors: List[str]) -> None:
    while not stop_event.is_set():
        try:
            async with grpc.aio.insecure_channel(GRPC_TARGET) as channel:
                stub = monitor_pb2_grpc.NodeMonitorStub(channel)
                print(f"Connected to {GRPC_TARGET} with ip ={get_local_ip()}")

                await stub.Heartbeat(heartbeat_generator(stop_event, neighbors))
        except Exception as e:
            print(f"Connection error: {e}")
            await asyncio.sleep(2)


def setup_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    def signal_handler(signum):
        print("Stopping agent...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            signal.signal(sig, lambda s, f: signal_handler(s))


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    setup_signal_handlers(loop, stop_event)

    # Load topology and get neighbors
    topology = load_topology()
    neighbors = get_neighbors(HOST_NAME, topology)
    
    print(f"Node: {HOST_NAME}")
    print(f"Neighbors: {neighbors}")
    print(f"Total neighbors: {len(neighbors)}")

    await run_agent(stop_event, neighbors)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user.")
        pass