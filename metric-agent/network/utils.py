import os
import random
import json
import math

NODE_TYPES = {
    "satellite": ["satellite"],
    "drone": ["drone"],
    "ground_station": ["ground", "station"],
    "mobile_device": ["mobile", "device"],
    "ship": ["ship"]
}

WEATHER_CONDITIONS = ["clear", "cloudy", "rainy", "stormy"]

WEATHER_IMPACT = {
    "clear": {"delay": 1.0, "jitter": 1.0, "loss": 1.0, "bandwidth": 1.0},
    "cloudy": {"delay": 1.05, "jitter": 1.2, "loss": 1.5, "bandwidth": 0.95},
    "rainy": {"delay": 1.15, "jitter": 1.5, "loss": 3.0, "bandwidth": 0.8},
    "stormy": {"delay": 1.3, "jitter": 2.0, "loss": 5.0, "bandwidth": 0.6}
}

JITTER_RANGES = {
    "satellite": (8, 20),       # High variability - orbital dynamics
    "drone": (10, 30),          # Movement and interference
    "ground_station": (1, 5),   # Stable infrastructure
    "mobile_device": (5, 15),   # Mobility
    "ship": (7, 20),            # Sea conditions
    "unknown": (5, 15)
}

QUEUE_CAPACITIES = {
    "satellite": (50, 200),      # High capacity processing
    "drone": (10, 50),           # Limited capacity
    "ground_station": (100, 500), # Very high capacity
    "mobile_device": (5, 30),    # Very limited
    "ship": (20, 100),           # Moderate capacity
    "unknown": (20, 100)
}

LINK_DELAYS = {
    ("satellite", "satellite"): (20, 50),
    ("satellite", "ground_station"): (250, 550),
    ("satellite", "drone"): (200, 400),
    ("satellite", "mobile_device"): (260, 500),
    ("satellite", "ship"): (270, 520),
    ("ground_station", "ground_station"): (10, 100),
    ("ground_station", "drone"): (30, 80),
    ("ground_station", "mobile_device"): (15, 50),
    ("ground_station", "ship"): (40, 120),
    ("drone", "drone"): (30, 150),
    ("drone", "mobile_device"): (25, 100),
    ("drone", "ship"): (50, 180),
    ("mobile_device", "mobile_device"): (20, 80),
    ("mobile_device", "ship"): (30, 100),
    ("ship", "ship"): (50, 200),
}

JITTER_RATIOS = {
    "satellite": 0.10,
    "drone": 0.15,
    "ground_station": 0.05,
    "mobile_device": 0.12,
    "ship": 0.13,
    "unknown": 0.10
}

BASE_LOSS_RATES = {
    "satellite": (0.001, 0.01),
    "drone": (0.005, 0.02),
    "ground_station": (0.0001, 0.001),
    "mobile_device": (0.002, 0.01),
    "ship": (0.003, 0.015),
    "unknown": (0.001, 0.01)
}

BANDWIDTH_RANGES = {
    ("satellite", "satellite"): (100, 500),
    ("satellite", "ground_station"): (50, 200),
    ("satellite", "drone"): (20, 100),
    ("ground_station", "ground_station"): (100, 1000),
    ("ground_station", "mobile_device"): (50, 300),
    ("drone", "drone"): (10, 50),
    ("mobile_device", "mobile_device"): (20, 100),
    ("ship", "ship"): (5, 50),
}

PROPAGATION_DELAYS = {
    "satellite": 0.0033,    # Radio waves through atmosphere to space
    "ground_fiber": 0.005,  # Optical fiber
    "wireless": 0.004       # Radio waves terrestrial
}

# Cache for topology data
_topology_cache = None

def load_topology() -> dict:
    global _topology_cache
    if _topology_cache is not None:
        return _topology_cache
    
    try:
        topology_path = "/topology/topology.json"
        if os.path.exists(topology_path):
            with open(topology_path, 'r') as f:
                _topology_cache = json.load(f)
                return _topology_cache
    except Exception as e:
        print(f"[WARN] Failed to load topology.json: {e}")
    
    return {"nodes": [], "links": []}


def get_node_info(hostname: str) -> dict:
    topology = load_topology()
    for node in topology.get("nodes", []):
        if node.get("id") == hostname:
            return {
                "lat": node.get("lat", 0.0),
                "lng": node.get("lng", 0.0),
                "weather": node.get("weather", "clear"),
                "type": node.get("type", "unknown")
            }
    
    return {
        "lat": float(os.getenv("LAT", "0")),
        "lng": float(os.getenv("LNG", "0")),
        "weather": os.getenv("WEATHER", "clear"),
        "type": "unknown"
    }


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return 6371.0 * c  # Earth radius in km


def get_node_type(hostname: str) -> str:
    hostname_lower = hostname.lower()
    
    for node_type, keywords in NODE_TYPES.items():
        if any(keyword in hostname_lower for keyword in keywords):
            return node_type
    
    return "unknown"


def get_weather_condition(hostname: str = None) -> str:
    if hostname:
        node_info = get_node_info(hostname)
        weather = node_info.get("weather", "").lower()
        if weather in WEATHER_CONDITIONS:
            return weather
    
    weather_env = os.getenv("WEATHER", "").lower()
    if weather_env in WEATHER_CONDITIONS:
        return weather_env

    return "clear"


def get_weather_impact(weather: str) -> dict:
    return WEATHER_IMPACT.get(weather, WEATHER_IMPACT["clear"])


def get_jitter_range(node_type: str) -> tuple:
    return JITTER_RANGES.get(node_type, JITTER_RANGES["unknown"])


def get_queue_capacity(node_type: str) -> tuple:
    return QUEUE_CAPACITIES.get(node_type, QUEUE_CAPACITIES["unknown"])


def get_link_delay_range(src_type: str, dst_type: str) -> tuple:
    link_key = tuple(sorted([src_type, dst_type]))
    return LINK_DELAYS.get(link_key, (50, 250))


def get_jitter_ratio(node_type: str) -> float:
    return JITTER_RATIOS.get(node_type, JITTER_RATIOS["unknown"])


def get_base_loss_rate(node_type: str) -> tuple:
    return BASE_LOSS_RATES.get(node_type, BASE_LOSS_RATES["unknown"])


def get_bandwidth_range(src_type: str, dst_type: str) -> tuple:
    link_key = tuple(sorted([src_type, dst_type]))
    return BANDWIDTH_RANGES.get(link_key, (10, 100))


def get_propagation_delay_factor(src_type: str, dst_type: str) -> float:
    if "satellite" in [src_type, dst_type]:
        return PROPAGATION_DELAYS["satellite"]
    elif src_type == "ground_station" and dst_type == "ground_station":
        return PROPAGATION_DELAYS["ground_fiber"]
    else:
        return PROPAGATION_DELAYS["wireless"]


def calculate_queue_utilization(cpu_percent: float) -> float:
    if cpu_percent > 80:
        return random.uniform(0.7, 0.9)
    elif cpu_percent > 60:
        return random.uniform(0.4, 0.7)
    elif cpu_percent > 30:
        return random.uniform(0.1, 0.4)
    else:
        return random.uniform(0.0, 0.2)
