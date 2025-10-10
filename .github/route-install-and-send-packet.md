## ⚙️ 1️⃣ Giao thức truyền gói tin – chọn cái “tự nhiên nhất”

### 🎯 Mục tiêu:

* Có thật trong Ubuntu (không phải custom framework).
* Dễ simulate.
* Cho phép gửi dữ liệu và metadata (hop count, src/dst, TTL…).
* Không cần root.

---

### 🧩 Ứng cử viên:

| Giao thức                    | Mô tả                      | Ưu điểm                            | Nhược điểm                          |
| ---------------------------- | -------------------------- | ---------------------------------- | ----------------------------------- |
| **UDP (socket)**             | Chuẩn mạng tầng transport  | nhanh, không kết nối, rất tự nhiên | không có xác nhận, phải tự code TTL |
| **TCP (socket)**             | kết nối có xác nhận        | dễ test, có đảm bảo delivery       | hơi nặng với routing nhiều hop      |
| **ICMP (ping / raw socket)** | mô phỏng gói điều khiển    | sát thực tế                        | cần quyền root                      |
| **ZeroMQ (PUB/SUB)**         | tiện simulation            | tiện trong test cluster            | framework, không “native Ubuntu”    |
| **Netcat (`nc`)**            | công cụ CLI, có sẵn Ubuntu | dùng được cho test nhanh           | không kiểm soát logic routing được  |

---

✅ **Kết luận:**

> Chọn **UDP sockets** (`socket.SOCK_DGRAM`)
> → “native” Ubuntu,
> → mô phỏng giống cách router forwarding,
> → nhẹ, không cần thiết lập connection,
> → có thể thêm TTL, hop count, checksum thủ công.

---
## ⚙️ 2️⃣ Mô hình gửi gói tin qua route

Giả sử route = `[node_A, node_B, node_C, node_D]`

```
A  --UDP-->  B  --UDP-->  C  --UDP-->  D
```

* Mỗi node agent có `UDPReceiver` đang lắng nghe.
* Khi nhận được gói:

  * Nếu `self.hostname == packet["dst"]`: in ra “📬 Delivered!”
  * Nếu không → gửi tiếp hop kế tiếp (`next_hop`).

---

## 🧭 5️⃣ Luồng hoạt động khi node gửi gói

```
1️⃣ Node A → gọi heuristic module:
    RequestRoute(src="A", dst="D")
         ↓
    → [A, B, C, D]

2️⃣ Node A → gửi UDP packet đầu tiên tới B:
    {
      src="A", dst="D", route=[A,B,C,D], hop_index=0
    }

3️⃣ Node B → nhận, hop_index=1, forward tới C

4️⃣ Node D → nhận, dst == self.hostname → ✅ Delivered
```

---

## ⚙️ 6️⃣ Kết hợp thực tế

Mỗi node agent của bạn:

* Có một **UDPReceiver** coroutine chạy nền (`asyncio.create_task()`).
* Có thể gửi gói qua `send_packet()` khi có nhiệm vụ.
* Giữ bảng ánh xạ hostname → IP trong `/topology/topology.json`.

---

## 🧩 7️⃣ Mô hình thực thi tổng thể

```
┌────────────┐
│ Node Agent │
│ (UDP + gRPC client) │
└──────┬─────┘
       │ RequestRoute(src,dst)
       ▼
┌────────────┐
│ Heuristic  │
│  gRPC srv  │
└──────┬─────┘
       │ Graph Snapshot
       ▼
┌────────────┐
│ Backend DB │
└────────────┘

(Sau đó node gửi thật qua UDP các hop)
```

---