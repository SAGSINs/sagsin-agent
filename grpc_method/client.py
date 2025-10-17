import asyncio
import socket
import grpc
from network.metrics import measure_links
from grpc_method.monitor_pb2 import LinkMetric, HeartbeatRequest, NodeMetric
from network.node_metrics import collect_node_metrics
from grpc_method.monitor_pb2_grpc import NodeMonitorStub
import os

def get_local_ip() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception:
        return "127.0.0.1"


async def heartbeat_generator(stop_event, neighbors):
    local_ip = get_local_ip()
    HOST_NAME = os.getenv("HOST_NAME", "unknown")
    INTERVAL_SEC = float(os.getenv("INTERVAL_SEC", "5.0"))
    LAT = float(os.getenv("LAT", "0.0"))
    LNG = float(os.getenv("LNG", "0.0"))

    while not stop_event.is_set():
        start_time = asyncio.get_event_loop().time()
        try:
            link_metrics = await measure_links(neighbors)
            links = [LinkMetric(**metric) for metric in link_metrics]

            node_metrics_data = await collect_node_metrics()
            node_metrics = NodeMetric(
                cpu_load=node_metrics_data.get("cpu_load", 0.0),
                jitter_ms=node_metrics_data.get("jitter_ms", 0.0),
                queue_len=node_metrics_data.get("queue_len", 0),
                throughput_mbps=node_metrics_data.get("throughput_mbps", 0.0),
            )

            yield HeartbeatRequest(
                ip=local_ip,
                hostname=HOST_NAME,
                links=links,
                node_metrics=node_metrics,
                lat=LAT,
                lng=LNG
            )

            elapsed_time = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, INTERVAL_SEC - elapsed_time)
            await asyncio.sleep(sleep_time)
        except Exception as e:
            print(f"[WARN] Error in heartbeat generator: {e}")
            elapsed_time = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, INTERVAL_SEC - elapsed_time)
            await asyncio.sleep(sleep_time)


async def stream_heartbeat(stub, stop_event, neighbors):
    try:
       await stub.Heartbeat(heartbeat_generator(stop_event, neighbors))
    except grpc.aio.AioRpcError as e:
        print(f"[ERROR] gRPC stream closed: {e.details()}")
    except asyncio.CancelledError:
        print("[WARN] Heartbeat task cancelled.")
    except Exception as e:
        print(f"[ERROR] Unexpected in stream_heartbeat: {e}")


async def run_agent(stop_event, neighbors):
    GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")
    print(f"Connecting to gRPC server at {GRPC_TARGET}")
    options = [
        ("grpc.keepalive_time_ms", 10000),
        ("grpc.keepalive_timeout_ms", 5000),
        ("grpc.keepalive_permit_without_calls", 1),
    ]

    while not stop_event.is_set():
        try:
            async with grpc.aio.insecure_channel(GRPC_TARGET, options=options) as channel:
                stub = NodeMonitorStub(channel)

                await stream_heartbeat(stub, stop_event, neighbors)
        except grpc.aio.AioRpcError as e:
            print(f"[WARN] gRPC connection error: {e.details()}")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[ERROR] Connection loop exception: {e}")
            await asyncio.sleep(2)