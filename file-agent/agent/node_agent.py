import socket
import struct
import json
import os
import threading
from typing import Dict
from .utils import (
    get_logger, calculate_md5, ensure_directory,
    get_timestamp, HOST_NAME, NODE_HOST, NODE_PORT, CHUNK_SIZE
)
from .sender import FileSender

logger = get_logger('agent.node_agent')

class NodeAgent:
    """
    TCP server that receives files and relays them to next hop
    """
    
    def __init__(
        self, 
        host: str = NODE_HOST, 
        port: int = NODE_PORT,
        receive_dir: str = 'receive-file',
        relay_dir: str = 'relay-cache'
    ):
        self.host = host
        self.port = port
        self.receive_dir = receive_dir
        self.relay_dir = relay_dir
        
        ensure_directory(receive_dir)
        ensure_directory(relay_dir)
        
        self.sender = FileSender(send_dir=relay_dir)
        self.running = False
        self.server_socket = None
    
    def start(self):
        """Start listening for incoming file transfers"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)  # Set timeout to allow checking self.running
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"🎧 Listening on {self.host}:{self.port} (Node: {HOST_NAME})")
        except OSError as e:
            logger.error(f"❌ Failed to bind to {self.host}:{self.port}: {e}")
            return

        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                logger.info(f"📥 Connection from {client_address}")

                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                thread.start()
            
            except socket.timeout:
                # Timeout is normal, just check self.running and continue
                continue
            except KeyboardInterrupt:
                logger.info("\n⚠️  Received interrupt signal")
                break
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Error accepting connection: {e}")
        
        self.stop()
    
    def stop(self):
        """Stop the server gracefully"""
        if not self.running:
            return
        
        logger.info("🛑 Stopping node agent...")
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
                logger.info("✅ Server socket closed")
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")
    
    def _handle_client(self, client_socket: socket.socket, client_address: tuple):
        try:
            metadata_len_bytes = self._recv_exact(client_socket, 4)
            if not metadata_len_bytes:
                logger.error("Failed to receive metadata length")
                return
            
            metadata_len = struct.unpack('!I', metadata_len_bytes)[0]
            
            # Receive metadata
            metadata_bytes = self._recv_exact(client_socket, metadata_len)
            if not metadata_bytes:
                logger.error("Failed to receive metadata")
                return
            
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            
            transfer_id = metadata['transfer_id']
            filename = metadata['filename']
            route = metadata['route']
            current_index = metadata['current_index']
            file_size = metadata['file_size']
            expected_md5 = metadata['md5']

            is_destination = current_index >= len(route) - 1
            
            # Save directory
            save_dir = self.receive_dir if is_destination else self.relay_dir
            save_path = os.path.join(save_dir, filename)
            
            # Receive file data
            bytes_received = 0
            with open(save_path, 'wb') as f:
                while bytes_received < file_size:
                    chunk_size = min(CHUNK_SIZE, file_size - bytes_received)
                    chunk = client_socket.recv(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
                    
                    # Progress
                    if bytes_received % (CHUNK_SIZE * 100) == 0:
                        progress = (bytes_received / file_size) * 100
                        logger.info(f"   Progress: {progress:.1f}%")
            
            logger.info(f"✅ File received: {bytes_received} bytes")
            
            # Verify MD5
            actual_md5 = calculate_md5(save_path)
            if actual_md5 != expected_md5:
                logger.error(f"❌ MD5 mismatch! Expected {expected_md5}, got {actual_md5}")
                self._send_ack(client_socket, False, "MD5 verification failed")
                return
            
            logger.info(f"✅ MD5 verified: {actual_md5}")
            
            # Send ACK
            self._send_ack(client_socket, True, "File received successfully")
            
            # If not destination, relay to next hop
            if not is_destination:
                logger.info(f"🔄 Relaying to next hop...")
                next_success = self.sender._send_to_next_hop(
                    file_path=save_path,
                    filename=filename,
                    transfer_id=transfer_id,
                    route=route,
                    current_index=current_index
                )
                
                if next_success:
                    logger.info(f"✅ Relay successful")
                    # Clean up relay cache
                    os.remove(save_path)
                else:
                    logger.error(f"❌ Relay failed")
            else:
                logger.info(f"🎯 Final destination reached. File saved to {save_path}")
                self._report_transfer_received(transfer_id, filename, route)
        
        except Exception as e:
            logger.error(f"❌ Error handling client: {e}")
            import traceback
            traceback.print_exc()
        finally:
            client_socket.close()
    
    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        data = b''
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def _send_ack(self, sock: socket.socket, success: bool, message: str):
        ack = {
            'status': 'OK' if success else 'ERROR',
            'message': message,
            'timestamp': get_timestamp()
        }
        ack_json = json.dumps(ack).encode('utf-8')
        sock.sendall(ack_json)
    
    def _report_transfer_received(self, transfer_id: str, filename: str, route: list):
        pass

# Singleton
_agent = None

def get_node_agent() -> NodeAgent:
    """Get or create singleton node agent"""
    global _agent
    if _agent is None:
        _agent = NodeAgent()
    return _agent
