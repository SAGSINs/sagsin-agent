"""Timeline gRPC client for sending file transfer updates"""
import grpc
from typing import Optional
from .utils import get_logger, HOST_NAME, get_timestamp
from proto import timeline_pb2, timeline_pb2_grpc
import os

logger = get_logger('agent.timeline_client')

class TimelineClient:
    """gRPC client to send timeline updates to backend"""
    
    def __init__(self):
        self.backend_url = os.getenv('TIMELINE_BACKEND_URL', 'localhost:50053')
        print( f"Timeline backend URL: {self.backend_url}" )
        self.channel = None
        self.stub = None
        
    def connect(self):
        """Establish gRPC connection"""
        try:
            self.channel = grpc.insecure_channel(self.backend_url)
            self.stub = timeline_pb2_grpc.TimelineServiceStub(self.channel)
            logger.info(f"✅ Connected to timeline service at {self.backend_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to timeline service: {e}")
    
    def send_update(
        self, 
        transfer_id: str, 
        hostname: Optional[str] = None,
        status: str = 'PENDING'
    ) -> bool:
        if not self.stub:
            self.connect()
        
        if not self.stub:
            logger.error("❌ No connection to timeline service")
            return False
        
        try:
            status_enum = timeline_pb2.Status.DONE if status.upper() == 'DONE' else timeline_pb2.Status.PENDING
            
            update = timeline_pb2.TimelineUpdate(
                transfer_id=transfer_id,
                hostname=hostname or HOST_NAME,
                timestamp=get_timestamp(),
                status=status_enum
            )
            
            self.stub.SendTimelineUpdate(update)      
        except grpc.RpcError as e:
            logger.error(f"❌ gRPC error sending timeline update: {e.code()} - {e.details()}")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending timeline update: {e}")
            return False
    
    def close(self):
        if self.channel:
            self.channel.close()
            logger.info("📴 Timeline client disconnected")

_timeline_client = None

def get_timeline_client() -> TimelineClient:
    global _timeline_client
    if _timeline_client is None:
        _timeline_client = TimelineClient()
        _timeline_client.connect()
    return _timeline_client
