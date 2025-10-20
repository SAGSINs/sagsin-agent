import os
import hashlib
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def get_config(key: str, default: Optional[str] = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Missing required config: {key}")
    return value

def calculate_md5(file_path: str) -> str:
    md5_hash = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        raise Exception(f"Failed to calculate MD5: {e}")

def get_file_size(file_path: str) -> int:
    return os.path.getsize(file_path)

def ensure_directory(dir_path: str) -> None:
    os.makedirs(dir_path, exist_ok=True)

def get_timestamp() -> str:
    return datetime.utcnow().isoformat() + 'Z'

# Configuration
HEURISTIC_ADDR = get_config('HEURISTIC_ADDR', 'localhost:50052')
HOST_NAME = get_config('HOST_NAME')
NODE_HOST = get_config('NODE_HOST', '0.0.0.0')
NODE_PORT = int(get_config('NODE_PORT', '7000'))
ALGORITHM = get_config('ALGORITHM', 'astar')
CHUNK_SIZE = int(get_config('CHUNK_SIZE', '8192'))
TRANSFER_TIMEOUT = int(get_config('TRANSFER_TIMEOUT', '30'))
TIMELINE_BACKEND_URL = get_config('TIMELINE_BACKEND_URL', 'localhost:50053')
