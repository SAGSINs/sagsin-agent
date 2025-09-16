import asyncio
import socket
import grpc
from network.metrics import measure_links
from grpc_method.monitor_pb2 import LinkMetric, HeartbeatRequest
from grpc_method.monitor_pb2_grpc import NodeMonitorStub
import os

def get_local_ip() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception:
        print("Failed to get local IP, defaulting to 127.0.0.1")

async def heartbeat_generator(stop_event, neighbors):
    local_ip = get_local_ip()
    HOST_NAME = os.getenv("HOST_NAME") or "unknown"
    INTERVAL_SEC = float(os.getenv("INTERVAL_SEC", "5.0"))
    while not stop_event.is_set():
        link_metrics = await measure_links(neighbors)
        links = [LinkMetric(**metric) for metric in link_metrics]
        yield HeartbeatRequest(
            ip=local_ip,
            hostname=HOST_NAME,
            links=links
        )
        await asyncio.sleep(INTERVAL_SEC)

async def run_agent(stop_event, neighbors):
    import os
    GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")
    while not stop_event.is_set():
        try:
            async with grpc.aio.insecure_channel(GRPC_TARGET) as channel:
                stub = NodeMonitorStub(channel)
                print(f"Connected to {GRPC_TARGET}")
                await stub.Heartbeat(heartbeat_generator(stop_event, neighbors))
        except Exception as e:
            print(f"Connection error: {e}")
            await asyncio.sleep(2)
