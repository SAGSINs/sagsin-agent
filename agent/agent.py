import asyncio
import os
import socket
import time
import logging
import signal
from typing import AsyncGenerator

import psutil
import grpc

try:
    from . import monitor_pb2, monitor_pb2_grpc
except ImportError:
    import monitor_pb2
    import monitor_pb2_grpc

# Configuration từ environment variables
GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")
NODE_ID = os.getenv("NODE_ID", socket.gethostname())
INTERVAL_SEC = float(os.getenv("INTERVAL_SEC", "5.0"))
RETRY_BACKOFF_SEC = float(os.getenv("RETRY_BACKOFF_SEC", "2.0"))
MAX_BACKOFF_SEC = float(os.getenv("MAX_BACKOFF_SEC", "60.0"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sagsin_agent.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    try:
        # Kết nối dummy để lấy IP local
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


async def heartbeat_generator(stop_event: asyncio.Event) -> AsyncGenerator[monitor_pb2.HeartbeatRequest, None]:

    local_ip = get_local_ip()
    hostname = socket.gethostname()
    
    logger.info(f"Starting heartbeat generator for node: {NODE_ID}")
    logger.info(f"Local IP: {local_ip}, Hostname: {hostname}")
    
    while not stop_event.is_set():
        try:
            request = monitor_pb2.HeartbeatRequest(
                node_id=NODE_ID,
                timestampMs=int(time.time() * 1000),
                ip=local_ip,
                hostname=hostname
            )
            
            logger.debug(f"Sending heartbeat: {NODE_ID} at {request.timestampMs}")
            yield request
            
            await asyncio.sleep(INTERVAL_SEC)
            
        except Exception as e:
            logger.error(f"Error generating heartbeat: {e}")
            await asyncio.sleep(1) 


async def run_agent(stop_event: asyncio.Event) -> None:
    backoff = RETRY_BACKOFF_SEC
    
    while not stop_event.is_set():
        try:
            logger.info(f"Connecting to gRPC server: {GRPC_TARGET}")
            
            async with grpc.aio.insecure_channel(GRPC_TARGET) as channel:
                stub = monitor_pb2_grpc.NodeMonitorStub(channel)
                
                logger.info(f"Opening heartbeat stream for node: {NODE_ID}")
                
                response = await stub.Heartbeat(heartbeat_generator(stop_event))
                
                logger.info(f"Server response - Success: {response.success}, Message: {response.message}")
                
                backoff = RETRY_BACKOFF_SEC
                
        except grpc.aio.AioRpcError as rpc_error:
            logger.warning(f"gRPC error: {rpc_error.code()} - {rpc_error.details()}")
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        # Dừng nếu nhận signal stop
        if stop_event.is_set():
            break
            
        # Exponential backoff cho retry
        logger.info(f"Reconnecting after {backoff}s backoff...")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF_SEC)


def setup_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    def signal_handler(signum):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        stop_event.set()
    
    try:
        if hasattr(signal, 'SIGTERM'):
            loop.add_signal_handler(signal.SIGTERM, lambda: signal_handler(signal.SIGTERM))
        if hasattr(signal, 'SIGINT'):
            loop.add_signal_handler(signal.SIGINT, lambda: signal_handler(signal.SIGINT))
    except NotImplementedError:
        # Windows không support add_signal_handler
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))


async def main() -> None:
    """
    Entry point chính của agent
    """
    logger.info("=" * 50)
    logger.info("SAGSIN Agent Starting...")
    logger.info(f"Target Server: {GRPC_TARGET}")
    logger.info(f"Node ID: {NODE_ID}")
    logger.info(f"Heartbeat Interval: {INTERVAL_SEC}s")
    logger.info("=" * 50)
    
    # Tạo event để điều khiển shutdown
    stop_event = asyncio.Event()
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    setup_signal_handlers(loop, stop_event)
    
    try:
        # Chạy agent
        await run_agent(stop_event)
    finally:
        logger.info("SAGSIN Agent stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user.")
    except Exception as e:
        logger.error(f"Agent failed: {e}")
