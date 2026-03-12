#!/usr/bin/env python3
"""
Octo CDP Bridge Manager

Purpose
-------
When Octo starts a profile for automation, it exposes a CDP WebSocket like:
  ws://127.0.0.1:PORT/devtools/browser/...

If your application runs in Docker, the container cannot connect to 127.0.0.1:PORT
on the host. This manager runs on the Octo host and creates small TCP bridges:

  container -> host:BRIDGE_PORT -> 127.0.0.1:PORT (Chromium CDP)

API
---
POST /bridge
  JSON body: { "target_port": <int> }
  Response:  { "port": <bridge_port_int> }

The manager chooses a free bridge port in a configured range and starts a
threaded TCP proxy that listens on 0.0.0.0:bridge_port and forwards to
127.0.0.1:target_port.

Run this on the same machine where Octo Browser is running.

# Enable ufw rules for the subnet where the container is running
# Example if subnet is 172.18.0.0/16:
sudo ufw allow from 172.18.0.0/16 to any port 58889 proto tcp
sudo ufw allow from 172.18.0.0/16 to any port 58890 proto tcp
sudo ufw allow from 172.18.0.0/16 to any port 60000:60100 proto tcp
sudo ufw reload
"""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple

LISTEN_HOST = "0.0.0.0"
MANAGER_PORT = 58890
BRIDGE_PORT_RANGE: Tuple[int, int] = (60000, 60100)  # inclusive lower, exclusive upper
TARGET_HOST = "127.0.0.1"


def log(msg: str) -> None:
    print(f"[octo-cdp-bridge] {msg}", flush=True)


def relay(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        try:
            src.close()
        except OSError:
            pass
        try:
            dst.close()
        except OSError:
            pass


def start_tcp_bridge(bridge_port: int, target_port: int) -> None:
    """Start a simple TCP bridge on 0.0.0.0:bridge_port -> 127.0.0.1:target_port."""

    def handle_client(client_sock: socket.socket) -> None:
        try:
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.connect((TARGET_HOST, target_port))
        except OSError as e:
            log(f"Failed to connect to CDP target {TARGET_HOST}:{target_port}: {e}")
            client_sock.close()
            return

        t1 = threading.Thread(target=relay, args=(client_sock, upstream), daemon=True)
        t2 = threading.Thread(target=relay, args=(upstream, client_sock), daemon=True)
        t1.start()
        t2.start()

    def server_loop() -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LISTEN_HOST, bridge_port))
        srv.listen(64)
        log(f"Bridge listening on {LISTEN_HOST}:{bridge_port} -> {TARGET_HOST}:{target_port}")
        while True:
            try:
                client, addr = srv.accept()
            except OSError:
                break
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()

    threading.Thread(target=server_loop, daemon=True).start()


def allocate_bridge_port(target_port: int) -> int:
    """Find a free port in BRIDGE_PORT_RANGE and start a bridge."""
    for port in range(BRIDGE_PORT_RANGE[0], BRIDGE_PORT_RANGE[1]):
        try:
            # Try to bind to check if port is free, then close immediately.
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.bind((LISTEN_HOST, port))
            test_sock.close()
        except OSError:
            continue

        # Port seems free; start bridge server on it.
        start_tcp_bridge(port, target_port)
        return port

    raise RuntimeError("No free bridge ports available in configured range")


class BridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/bridge":
            self._send_json(404, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        target_port = data.get("target_port")
        if not isinstance(target_port, int) or not (1 <= target_port <= 65535):
            self._send_json(400, {"error": "invalid_target_port"})
            return

        try:
            bridge_port = allocate_bridge_port(target_port)
        except RuntimeError as e:
            log(str(e))
            self._send_json(503, {"error": "no_bridge_ports_available"})
            return

        log(f"Created bridge {LISTEN_HOST}:{bridge_port} -> {TARGET_HOST}:{target_port}")
        self._send_json(200, {"port": bridge_port})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Silence default HTTP server logging; we use our own logger.
        return


def main() -> None:
    addr = (LISTEN_HOST, MANAGER_PORT)
    log(f"Starting Octo CDP bridge manager on {addr[0]}:{addr[1]}")
    log(f"Bridge port range: {BRIDGE_PORT_RANGE[0]}-{BRIDGE_PORT_RANGE[1] - 1}")
    httpd = HTTPServer(addr, BridgeHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down bridge manager")
        httpd.server_close()


if __name__ == "__main__":
    main()

