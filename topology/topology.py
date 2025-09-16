import json
from typing import Dict, List

def load_topology(path: str) -> Dict:
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading topology: {e}")
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
    return list(set(neighbors))
