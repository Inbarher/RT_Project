# Network Protocols: Reliable Frame Streaming

An end-to-end networking project that simulates the path from joining a network to streaming visual content. A Python client obtains a simulated IP address through a custom DHCP-like service, resolves a service name through a local DNS-like service, and then streams image frames over either TCP or a reliable UDP protocol implemented at the application layer.

> **Course-project scope.** This repository intentionally simulates selected networking concepts. Its DHCP and DNS messages are custom text protocols, not interoperable implementations of the standard DHCP or DNS wire protocols.

![Example streamed frame](frame_1.png)

## Highlights

- **Custom DHCP-like handshake:** `DISCOVER` → `OFFER` → `REQUEST` → `ACK` over UDP.
- **Local DNS-like resolution:** resolves `my_app.com` to the video service address.
- **TCP streaming:** sends a frame count followed by length-prefixed PNG frames.
- **Reliable UDP streaming:** sequence numbers, acknowledgements, client-advertised receive window, buffering of out-of-order packets, retransmission on timeout, and frame-completion confirmation.
- **Congestion-control ideas over UDP:** slow start, a congestion threshold, additive increase, timeout backoff, and fast retransmit after three duplicate ACKs.
- **Multiple qualities:** source frames can be generated as `High`, `Med`, and `Low` PNG variants.

## Architecture

```text
                         UDP : 6767
                  +---------------------+
                  | DHCP-like server    |
                  | IP pool / leases    |
                  +----------+----------+
                             |
     DISCOVER / OFFER / REQUEST / ACK
                             |
                             v
+----------------+     UDP : 9999      +---------------------+
| Python client  +---------------------> DNS-like server     |
|                |   my_app.com lookup  | local name table    |
+-------+--------+                      +----------+----------+
        |                                          |
        | resolved video-service address           |
        v                                          v
  +----------------------------------------------------------+
  | Video server                                             |
  | TCP 8080: length-prefixed PNG frames                     |
  | UDP 8081: reliable, windowed PNG-frame transport         |
  +----------------------------------------------------------+
```

## Repository layout

| File | Responsibility |
| --- | --- |
| `client.py` | Runs network discovery, lets the user select content and quality, and plays/saves received frames. |
| `dhcp_server.py` | Maintains a small in-memory IP pool and performs the custom DHCP-style exchange. |
| `dns_server.py` | Resolves `my_app.com` from its local table. |
| `video_server.py` | Hosts TCP and reliable-UDP streaming services concurrently. |
| `setup_assets.py` | Creates medium- and low-resolution PNG copies from `High` source frames. |
| `frame_*.png` | Example presentation frames used as streaming assets. |

## Protocol details

### 1. Address discovery

The client broadcasts `DISCOVER`. The DHCP-like server selects a free address from its in-memory pool (`192.168.1.100`–`192.168.1.102`) and responds with:

```text
OFFER|<offered-ip>|MY_APP_SERVER
```

The client requests the offered address and receives `ACK|<ip>`. This models the negotiation flow; it does **not** configure the machine's real network interface.

### 2. Name resolution

The client asks the local service for `my_app.com`. The server resolves that name from `dns_table` in `dns_server.py`. The fallback branch is illustrative only: it does not construct a standards-compliant DNS query and returns a placeholder response.

### 3. Frame delivery

**TCP** uses a simple framing protocol:

```text
<number-of-frames>#
<frame-size>#<png-bytes>
```

**UDP** splits each PNG into 512-byte chunks. Each chunk is sent as `<sequence-number>|<bytes>#`; the client returns acknowledgements such as `ACK|<last-in-order-sequence>|WIN=<free-slots>#`. An `END|<sequence-number>#` marker closes each frame and is itself acknowledged.

## Requirements

- Python 3.10+
- `numpy`
- `opencv-python`
- `Pillow`

Install the dependencies:

```bash
python -m pip install numpy opencv-python Pillow
```

## Prepare the media assets
