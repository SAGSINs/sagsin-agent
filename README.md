# SAGSIN Agent

Unified Docker agent chạy đồng thời **metric monitoring** và **file transfer** cho mạng lưới phân tán SAGSIN.

## 🎯 Giới Thiệu

SAGSIN Agent là multi-purpose node agent gồm 2 thành phần chính:
- **Metric Agent**: Heartbeat monitoring, thu thập metrics (CPU, RAM, network, disk)
- **File Agent**: Hop-by-hop file transfer với heuristic routing

Mỗi container agent đại diện cho 1 node trong topology (satellite, drone, ground station, mobile device, ship).

## 🏗️ Kiến Trúc

```
sagsin-agent/
├── metric-agent/           # Metric monitoring agent
│   ├── core/
│   │   └── agent.py       # Main heartbeat agent
│   ├── grpc_method/       # gRPC generated code
│   ├── network/           # Network metrics collector
│   ├── topology/          # Topology manager
│   └── requirements.txt   # grpcio, psutil
│
├── file-agent/            # File transfer agent
│   ├── agent/
│   │   ├── node_agent.py  # TCP server (receive & relay)
│   │   ├── sender.py      # File sender
│   │   ├── grpc_client.py # Heuristic gRPC client
│   │   └── utils.py       # Utilities
│   ├── proto/             # gRPC proto definitions
│   ├── send-file/         # Source files directory
│   ├── receive-file/      # Destination files directory
│   ├── relay-cache/       # Temporary relay cache
│   ├── main.py            # CLI entry point
│   └── requirements.txt   # grpcio, python-dotenv
│
├── Dockerfile             # Multi-stage unified build
├── docker-entrypoint.sh   # Dual-agent launcher
└── README.md             # This file
```

## 🔧 Cơ Chế Hoạt Động

### Metric Agent
1. Kết nối gRPC stream với backend (port 50051)
2. Gửi heartbeat mỗi 5 giây với metrics:
   - CPU usage, load average
   - RAM used/available
   - Network bandwidth (tx/rx bytes, packets)
   - Disk usage
3. Đọc topology.json để xác định neighbors
4. Auto-retry với exponential backoff khi mất kết nối

### File Agent
1. Listen trên port 7000 cho incoming transfers
2. Query heuristic service (port 50052) để tìm optimal route
3. Transfer file theo route với MD5 verification
4. Report timeline events tới backend (port 50053)
5. Cache files khi relay sang node tiếp theo

## 🚀 Hướng Dẫn Chạy

### Docker (Production Mode)

```bash
# Build unified image
docker build -t sagsin-agent .
```

### Development (Metric Agent)

```bash
cd metric-agent

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Generate gRPC code
python -m grpc_tools.protoc -I./proto \
  --python_out=grpc_method \
  --grpc_python_out=grpc_method \
  proto/monitor.proto

# Run agent
export GRPC_TARGET=localhost:50051
export HOST_NAME=test_node
export LAT=21.0285
export LNG=105.8542
python -m core.agent
```

### Development (File Agent)

```bash
cd file-agent

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set HEURISTIC_ADDR, HOST_NAME, NODE_PORT

# Start listener
python main.py listen

# Send file (in another terminal)
echo "Test message" > send-file/test.txt
python main.py send test.txt destination_node --algo astar
```

## 🌍 Environment Variables

### Metric Agent
```bash
GRPC_TARGET=192.168.100.10:50051    # Backend gRPC endpoint
HOST_NAME=ground_station_hanoi      # Node identifier
LAT=21.0285                         # GPS latitude
LNG=105.8542                        # GPS longitude
INTERVAL_SEC=5                      # Heartbeat interval
RETRY_BACKOFF_SEC=2                # Initial retry delay
MAX_BACKOFF_SEC=30                 # Max retry delay
TOPOLOGY_FILE=/topology/topology.json
```

### File Agent
```bash
HEURISTIC_ADDR=192.168.100.3:50052      # Heuristic gRPC server
TIMELINE_BACKEND_URL=192.168.100.10:50053  # Timeline tracking
NODE_HOST=0.0.0.0                       # Bind address
NODE_PORT=7000                          # TCP listen port
ALGORITHM=astar                         # Routing algorithm
```

## 📊 Kết Quả Đạt Được

### ✅ Features

1. **Dual-Agent Architecture**: Chạy đồng thời metric + file agent trong 1 container
2. **Real-time Monitoring**: Heartbeat mỗi 5s với comprehensive metrics
3. **Hop-by-Hop Transfer**: File transfer qua multiple hops với MD5 integrity
4. **Smart Routing**: Tích hợp heuristic service cho optimal path finding
5. **Timeline Tracking**: Millisecond-precision tracking từng hop transfer
6. **Auto-reconnect**: Exponential backoff retry cho network failures
7. **Graceful Shutdown**: Signal handling đúng chuẩn (SIGTERM/SIGINT)

### 🔍 Monitoring Capabilities

- **Node Discovery**: Auto-register với backend khi startup
- **Health Status**: Live/Dead detection dựa trên heartbeat
- **Network Metrics**: Bandwidth usage, packet counts, errors
- **System Metrics**: CPU load, RAM usage, disk space
- **Transfer History**: Timeline view với status tracking

## 🛠️ File Transfer Flow

```
┌──────────────────────┐
│  ground_station_hanoi │
│  Send: message.txt    │
└─────────┬────────────┘
          │
          ├─1. Query route → sagsin-heuristic (gRPC)
          │   Response: [hanoi, satellite, ship]
          │
          ├─2. TCP Connect → satellite:7000
          │   ├─ Send file header (filename, size, MD5)
          │   ├─ Send file chunks
          │   └─ Report timeline: PENDING
          │
          ↓
┌──────────────────┐
│  satellite_leo   │
│  Relay Cache     │
└─────────┬────────┘
          │
          ├─3. Receive & verify MD5
          ├─4. Cache in relay-cache/
          ├─5. TCP Connect → ship:7000
          │   └─ Forward file
          │
          ↓
┌──────────────────┐
│  ship_tokyo      │
│  Final Dest      │
└─────────┬────────┘
          │
          ├─6. Receive & verify MD5
          ├─7. Save to receive-file/
          └─8. Report timeline: DONE

Total: 3 hops, <200ms
```

## 📝 Notes

- Agents tự động start cả metric và file services qua entrypoint script
- Topology file phải được mount vào `/topology/topology.json`
- Custom hosts file cần mapping IP → hostname cho tất cả nodes
- File agent port 7000 phải được expose ra ngoài container
- MD5 checksum đảm bảo integrity cho mọi file transfer
- Timeline events được gửi qua gRPC tới backend port 50053

---

**Docker Hub**: `baocules/sagsin-agent`  
**Dependencies**: Python 3.11, gRPC, psutil, python-dotenv
