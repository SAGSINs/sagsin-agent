import asyncio
import os
import socket
import signal
from typing import AsyncGenerator

import grpc

try:
    from . import monitor_pb2, monitor_pb2_grpc
except ImportError:
    import monitor_pb2
    import monitor_pb2_grpc

# Config
GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")
INTERVAL_SEC = float(os.getenv("INTERVAL_SEC", "5.0"))

def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


async def heartbeat_generator(stop_event: asyncio.Event) -> AsyncGenerator[monitor_pb2.HeartbeatRequest, None]:
    local_ip = get_local_ip()
    hostname = socket.gethostname()

    while not stop_event.is_set():
        yield monitor_pb2.HeartbeatRequest(
            ip=local_ip,
            hostname=hostname
        )
        await asyncio.sleep(INTERVAL_SEC)


async def run_agent(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with grpc.aio.insecure_channel(GRPC_TARGET) as channel:
                stub = monitor_pb2_grpc.NodeMonitorStub(channel)
                print(f"Connected to {GRPC_TARGET} with ip ={get_local_ip()}")

                await stub.Heartbeat(heartbeat_generator(stop_event))
        except Exception as e:
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

    await run_agent(stop_event)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user.")
        pass