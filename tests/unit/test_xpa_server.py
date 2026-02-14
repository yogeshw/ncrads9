import socket

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
