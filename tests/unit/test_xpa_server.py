import socket
import threading
import time

from ncrads9.communication.xpa.xpa_server import XPAServer


def _send_command(host: str, port: int, command: str) -> str:
    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(command.encode("utf-8"))
        client.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            data = client.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("utf-8").strip()


def test_xpa_server_roundtrip_and_meta_commands():
    server = XPAServer(name="ncrads9-test", host="127.0.0.1", port=0)
    server.register_handler("ping", lambda **params: f"pong {params.get('value', '')}".strip())
    assert server.start()
    try:
        pong = _send_command(server.host, server.port, "ping value=42\n")
        assert pong == "pong 42"

        access = _send_command(server.host, server.port, "xpaaccess ncrads9-test\n")
        assert "ncrads9-test" in access
        assert str(server.port) in access

        info = _send_command(server.host, server.port, "xpainfo ncrads9-test\n")
        assert "file" in info
        assert "zoom" in info
    finally:
        server.stop()


# -- denial-of-service hardening -----------------------------------------------


def test_a_request_without_a_newline_is_bounded_not_unbounded():
    """A client that never sends a newline used to make the receive loop
    accumulate for the whole socket timeout with no cap on memory."""
    server = XPAServer(name="ncrads9-dos", host="127.0.0.1", port=0)
    # A tiny cap so the test sends kilobytes, not gigabytes, to trip it.
    server.MAX_REQUEST_BYTES = 4096
    assert server.start()
    try:
        with socket.create_connection((server.host, server.port), timeout=5) as client:
            # No newline, larger than the cap: the server refuses it and
            # closes, rather than buffering everything sent.
            try:
                client.sendall(b"x" * 200000)
                client.shutdown(socket.SHUT_WR)
                reply = client.recv(4096)
            except (ConnectionResetError, BrokenPipeError):
                # The server closed on the refused request mid-send, which is
                # the point: it did not sit there buffering. Also a refusal.
                reply = b""
        # The over-cap request is dropped, so there is no response.
        assert reply == b""
    finally:
        server.stop()

    # And a normal request still works after the cap is restored.
    server = XPAServer(name="ncrads9-dos2", host="127.0.0.1", port=0)
    server.register_handler("ping", lambda **params: "pong")
    assert server.start()
    try:
        assert _send_command(server.host, server.port, "ping\n") == "pong"
    finally:
        server.stop()


def test_connections_over_the_limit_are_dropped_not_queued_as_threads():
    """Each connection is a thread; without a cap a flood is a thread flood.

    A handler is made to block so the slots stay taken, then one more
    connection is opened: it must be closed at once rather than accepted
    into a new handler thread.
    """
    release = threading.Event()

    server = XPAServer(name="ncrads9-cap", host="127.0.0.1", port=0)
    server.MAX_CONNECTIONS = 2
    # Rebuild the semaphore for the lowered limit.
    server._connection_slots = threading.BoundedSemaphore(server.MAX_CONNECTIONS)
    server.register_handler("hold", lambda **params: release.wait(timeout=5.0) and "done")
    assert server.start()

    held: list[socket.socket] = []
    try:
        # Fill both slots with connections whose handler is blocked.
        for _ in range(2):
            client = socket.create_connection((server.host, server.port), timeout=5)
            client.sendall(b"hold\n")
            held.append(client)
        # Give the two handlers time to start and take their slots.
        time.sleep(0.5)

        # A third connection is over the limit: the server closes it, so a
        # read returns end-of-stream promptly rather than hanging.
        with socket.create_connection((server.host, server.port), timeout=5) as extra:
            extra.settimeout(3.0)
            assert extra.recv(1024) == b""
    finally:
        release.set()
        for client in held:
            client.close()
        server.stop()


def test_abandoned_transactions_do_not_grow_without_bound():
    """A client that begins xpaset/xpaget transactions but never sends the
    second stage used to leave an entry behind for each, forever."""
    server = XPAServer(name="ncrads9-pending", host="127.0.0.1", port=0)
    server.MAX_PENDING_TRANSACTIONS = 4
    assert server.start()
    try:
        # Start more transactions than the cap, none of them ever completed.
        for _ in range(20):
            _send_command(server.host, server.port, "get zoom\nxpa_id=x0\n")
        # The table is held to the cap rather than growing to twenty.
        assert len(server._pending_requests) <= server.MAX_PENDING_TRANSACTIONS
    finally:
        server.stop()
