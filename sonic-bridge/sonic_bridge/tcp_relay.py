"""TCP line relay for WSL→Windows Unity (mirrored WSL cannot UDP to Windows host)."""

from __future__ import annotations

import socket
import threading


class TcpLineRelay:
    """Accept TCP clients; broadcast newline-terminated JSON lines."""

    def __init__(self, host: str = "0.0.0.0", port: int = 17782) -> None:
        self._running = True
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.listen(8)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        print(f"[TcpRelay] listening on {host}:{port} (Windows: unity_udp_relay.ps1)")

    def _accept_loop(self) -> None:
        self._server.settimeout(1.0)
        while self._running:
            try:
                conn, addr = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self._lock:
                self._clients.append(conn)
            print(f"[TcpRelay] client {addr[0]}:{addr[1]} ({len(self._clients)} connected)")

    def broadcast(self, payload: bytes) -> None:
        if not payload:
            return
        line = payload if payload.endswith(b"\n") else payload + b"\n"
        dead: list[socket.socket] = []
        with self._lock:
            for conn in self._clients:
                try:
                    conn.sendall(line)
                except OSError:
                    dead.append(conn)
            for conn in dead:
                self._clients.remove(conn)
                try:
                    conn.close()
                except OSError:
                    pass

    def close(self) -> None:
        self._running = False
        try:
            self._server.close()
        except OSError:
            pass
        with self._lock:
            for conn in self._clients:
                try:
                    conn.close()
                except OSError:
                    pass
            self._clients.clear()
