import socket
import os
import struct
import json
import uuid
from typing import List
from .utils import (
    get_logger, calculate_md5, get_file_size, 
    get_timestamp, CHUNK_SIZE, TRANSFER_TIMEOUT, HOST_NAME
)
from .grpc_client import get_heuristic_client
from .utils import NODE_PORT
from .timeline_client import get_timeline_client

logger = get_logger('agent.sender')

class FileSender:
    """Handles file sending through multiple hops"""
    
    def __init__(self, send_dir: str = 'send-file'):
        self.send_dir = send_dir
        os.makedirs(send_dir, exist_ok=True)
    
    def send_file_to_destination(
        self, 
        filename: str, 
        destination: str,
        algorithm: str = 'astar'
    ) -> bool:
        file_path = os.path.join(self.send_dir, filename)
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        logger.info(f"Starting file transfer: {filename} → {destination}")
        logger.info(f"   Source: {HOST_NAME}")

        client = get_heuristic_client()
        route = client.find_route(HOST_NAME, destination, algorithm)
        
        if not route or len(route) < 2:
            logger.error(f"No valid route found to {destination}")
            return False
        
        if route[0] != HOST_NAME:
            logger.error(f"Route source {route[0]} doesn't match current node {HOST_NAME}")
            return False
        
        transfer_id = str(uuid.uuid4())
        
        success = self._send_to_next_hop(
            file_path=file_path,
            filename=filename,
            transfer_id=transfer_id,
            route=route,
            current_index=0
        )
        
        if success:
            logger.info(f"File sent successfully: {transfer_id}")
            self._send_timeline_update(transfer_id, "PENDING")
        else:
            logger.error(f"File transfer failed: {transfer_id}")
        
        return success
    
    def _send_to_next_hop(
        self,
        file_path: str,
        filename: str,
        transfer_id: str,
        route: List[str],
        current_index: int
    ) -> bool:
        if current_index >= len(route) - 1:
            logger.error("Already at destination")
            return False
        
        next_hop = route[current_index + 1]

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TRANSFER_TIMEOUT)
            sock.connect((next_hop, NODE_PORT))
            
            file_size = get_file_size(file_path)
            file_md5 = calculate_md5(file_path)
            
            metadata = {
                'transfer_id': transfer_id,
                'filename': filename,
                'route': route,
                'current_index': current_index + 1, 
                'file_size': file_size,
                'md5': file_md5,
                'timestamp': get_timestamp()
            }
            
            metadata_json = json.dumps(metadata).encode('utf-8')
            
            sock.sendall(struct.pack('!I', len(metadata_json)))
            sock.sendall(metadata_json)

            bytes_sent = 0
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    sock.sendall(chunk)
                    bytes_sent += len(chunk)

            ack_data = sock.recv(1024)
            ack = json.loads(ack_data.decode('utf-8'))
            
            if ack.get('status') == 'OK':
                return True
            else:
                logger.error(f"NACK received: {ack.get('message')}")
                return False
        
        except socket.timeout:
            logger.error(f"Timeout connecting to {next_hop}")
            return False
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            return False
        finally:
            sock.close()
    
    def _send_timeline_update(self, transfer_id: str, status: str):
        try:
            timeline_client = get_timeline_client()
            timeline_client.send_update(
                transfer_id=transfer_id,
                hostname=HOST_NAME,
                status=status
            )
        except Exception as e:
            logger.error(f"Error sending timeline update: {e}")

# Singleton instance
_sender = None

def get_file_sender() -> FileSender:
    global _sender
    if _sender is None:
        _sender = FileSender()
    return _sender
