import grpc
import sys
import os
from typing import Optional, Callable, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from proto import algorithm_stream_pb2, algorithm_stream_pb2_grpc
from .utils import get_logger, HEURISTIC_ADDR, ALGORITHM

logger = get_logger('agent.grpc_client')

class HeuristicClient:
    def __init__(self, server_address: str = HEURISTIC_ADDR):
        self.server_address = server_address
        self.channel = None
        self.stub = None
    
    def connect(self):
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = algorithm_stream_pb2_grpc.AlgorithmStreamServiceStub(self.channel)
        except Exception as e:
            logger.error(f"❌ Failed to connect to heuristic server: {e}")
            raise
    
    def find_route(
        self, 
        src: str, 
        dst: str, 
        algorithm: str = ALGORITHM,
        on_step: Optional[Callable] = None
    ) -> Optional[List[str]]:
        if not self.stub:
            self.connect()
        try:
            request = algorithm_stream_pb2.AlgorithmRunRequest(
                algo=algorithm,
                src=src,
                dst=dst
            )
            
            stream = self.stub.RunAlgorithm(request)
            
            route_path = None
            
            for event in stream:
                if event.HasField('run_start'):
                    pass
                
                elif event.HasField('step'):
                    step = event.step
                    if on_step:
                        on_step(step)
                
                elif event.HasField('complete'):
                    complete = event.complete
                    if complete.result and complete.result.path:
                        route_path = list(complete.result.path)
            
            return route_path
        
        except grpc.RpcError as e:
            logger.error(f"❌ gRPC error: {e.code()} - {e.details()}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            raise
    
    def close(self):
        if self.channel:
            self.channel.close()

_client = None

def get_heuristic_client() -> HeuristicClient:
    global _client
    if _client is None:
        _client = HeuristicClient()
        _client.connect()
    return _client
