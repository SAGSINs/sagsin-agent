## 🧭 Mục tiêu tổng thể

* Triển khai và duy trì một **gRPC agent nhẹ** dùng để:

  1. Thu thập và gửi telemetry (metrics) về backend.
  2. Gửi **gói dữ liệu thực** giữa các node qua **UDP socket**.
  3. Gọi **heuristic module** để lấy route tối ưu trước khi truyền gói.
* Code phải tối giản, có type hints, dễ test, sẵn sàng chạy trong container hoặc local.
* Cung cấp tài liệu rõ ràng, Dockerfile nhỏ gọn, và test core behaviors (metrics, route, forwarding).

---

## 🏗️ Tổng quan kiến trúc

```
        ┌────────────────────────────────────────┐
        │              SAGSIN AGENT              │
        │----------------------------------------│
        │ CLI / Entrypoint (run_agent.py / .bat) │
        │----------------------------------------│
        │ Agent Core (agent/agent.py)            │
        │----------------------------------------│
        │ gRPC client (monitor_pb2_grpc.py)      │
        │----------------------------------------│
        │ Metrics collectors (cpu, net, disk)    │
        │----------------------------------------│
        │ UDP Router (udp_router.py)             │
        │----------------------------------------│
        │ Heuristic client (heuristic_pb2_grpc)  │
        │----------------------------------------│
        │ Config & Logging                       │
        └────────────────────────────────────────┘
```

---

## 🧰 Ngôn ngữ & Frameworks

| Thành phần           | Mục đích                                 | Lý do chọn                                 |
| -------------------- | ---------------------------------------- | ------------------------------------------ |
| **Python 3.10+**     | ngôn ngữ chính                           | đơn giản, mạnh về async & gRPC             |
| **grpc.aio**         | giao tiếp với backend + heuristic module | async-native, dễ tích hợp                  |
| **socket (UDP)**     | truyền file/gói tin giữa các node        | nhẹ, có sẵn trong Ubuntu, mô phỏng thực tế |
| **loguru / logging** | logging có màu, dễ debug                 | rõ pipeline gửi/nhận                       |
| **asyncio**          | coroutine event loop                     | chạy song song listener và metric agent    |

---

## 📁 Cấu trúc thư mục (mở rộng)

```
sagsin-agent/
├── agent/
│   ├── __init__.py
│   ├── agent.py              # logic chính: collect + send heartbeat
│   ├── monitor_pb2.py        # protobuf backend
│   ├── monitor_pb2_grpc.py
│   ├── heuristic_pb2.py      # protobuf heuristic module
│   ├── heuristic_pb2_grpc.py
│   ├── udp_router.py         # gửi/nhận gói tin qua UDP
│   ├── packet.py             # định nghĩa cấu trúc packet
│   ├── topology.py           # load file topology.json (ip/neighbor mapping)
│   └── utils.py              # logger, config helpers
├── run_agent.py
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🧩 Luồng hoạt động tổng thể

```
1️⃣ Agent thu thập metrics định kỳ
    ↓
2️⃣ Gửi heartbeat qua gRPC → Backend
    ↓
3️⃣ Backend gửi graph snapshot → Heuristic Module
    ↓
4️⃣ Khi node muốn gửi file/gói tin:
      ├── Gọi gRPC tới Heuristic Module: RequestRoute(src, dst)
      ├── Nhận route [A, B, C, D]
      ├── Gửi file qua UDP hop-by-hop: A→B→C→D
      └── Mỗi node trung gian forward gói tin theo route
```

---

## ✅ Developer hướng dẫn cho Copilot / AI assistant

* **Code Python thuần** (asyncio + socket + grpc.aio).
* **Không dùng framework ngoài chuẩn Ubuntu**.
* Giữ mỗi file ~100–200 dòng, có docstring rõ.

* Khi cần thay đổi schema gRPC:

  ```bash
  python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. heuristic.proto