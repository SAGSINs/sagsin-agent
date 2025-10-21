# SAGSIN File Agent

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
### 3. Start Node Agent (Listen Mode)

```bash
python main.py listen
```
### 4. Send a File

In another terminal (or on source node):

```bash
# Place file in send-file/ directory
echo "Hello from Hanoi!" > send-file/a.txt

# Send to destination
python file-agent/main.py send a.txt ship_tokyo --algo astar
python main.py send a.txt ship_tokyo --algo astar
python main.py send a.txt drone_bejing --algo dijkstra
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
