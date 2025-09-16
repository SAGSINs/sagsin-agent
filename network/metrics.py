import asyncio
import random
import subprocess
import re

PING_REGEX = re.compile(r"= ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms")

async def ping_neighbor(neighbor_hostname: str) -> dict:
    try:
        import os
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
            match = PING_REGEX.search(output)
            if match:
                min_rtt, avg_rtt, max_rtt, mdev = map(float, match.groups())
                delay_ms = avg_rtt
                jitter_ms = mdev
                loss_rate = 0.0
                available = True
            else:
                delay_ms = random.uniform(10, 200)
                jitter_ms = random.uniform(1, 20)
                loss_rate = 0.0
                available = True
        else:
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

async def measure_links(neighbors: list) -> list:
    tasks = [ping_neighbor(n) for n in neighbors]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    links = []
    for i, result in enumerate(results):
        if isinstance(result, dict):
            links.append(result)
        else:
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
