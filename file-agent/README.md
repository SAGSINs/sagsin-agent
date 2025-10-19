# SAGSIN File Agent

Hop-by-hop file transfer system using heuristic routing from `sagsin-heuristic`.

## 🎯 Overview

This agent enables reliable file transfer across a network topology by:
1. Querying optimal route from heuristic service (gRPC)
2. Transferring files hop-by-hop via TCP
3. Verifying integrity with MD5 checksums
4. Reporting transfer status to monitoring

## 📁 Architecture

```
sagsin-file-agent/
├── agent/
│   ├── node_agent.py      # TCP server (receive & relay)
│   ├── sender.py          # File sender (initiate transfer)
│   ├── grpc_client.py     # gRPC client to heuristic
│   └── utils.py           # Config, logging, helpers
├── proto/                 # gRPC proto files
├── send-file/            # Place files to send here
├── receive-file/         # Final destination files
├── relay-cache/          # Temporary cache for relaying
├── main.py              # CLI entry point
└── .env                 # Configuration

```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd sagsin-file-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Heuristic gRPC Server
HEURISTIC_ADDR=localhost:50052

# Current Node
HOST_NAME=ground_station_hanoi
NODE_HOST=0.0.0.0
NODE_PORT=7000

# Algorithm
ALGORITHM=astar
```

### 3. Start Node Agent (Listen Mode)

```bash
python main.py listen
```
### 4. Send a File

In another terminal (or on source node):

```bash
# Place file in send-file/ directory
echo "Hello from Hanoi!" > file-agent/send-file/a.txt

# Send to destination
python file-agent/main.py send message.txt ship_tokyo --algo astar
python file-agent/main.py send a.txt ship_tokyo --algo astar
python file-agent/main.py send a.txt drone_bejing --algo dijkstra
```

## 📡 Transfer Flow

```
[ground_station_hanoi]
   └── Query route → sagsin-heuristic (gRPC)
         ↓
       Route: [ground_hanoi, satellite_leo, ship_tokyo]
         ↓
   └── TCP → satellite_leo:7002
              ↓ (receive & relay)
            TCP → ship_tokyo:7003
                   ↓ (receive & save)
                 [receive-file/message.txt]
```
