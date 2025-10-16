import asyncio
import os
import signal
from topology.topology import load_topology, get_neighbors
from grpc_method.client import run_agent

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
    HOST_NAME = os.getenv("HOST_NAME") or "unknown"
    TOPOLOGY_FILE = os.getenv("TOPOLOGY_FILE", "/topology/topology.json")
    topology = load_topology(TOPOLOGY_FILE)
    neighbors = get_neighbors(HOST_NAME, topology)
    await run_agent(stop_event, neighbors)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user.")
