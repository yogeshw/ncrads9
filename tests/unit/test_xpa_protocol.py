from ncrads9.communication.xpa.xpa_protocol import XPAProtocol


def test_parse_xpaget_request():
    protocol = XPAProtocol()
    request = protocol.parse_request(b"xpaget ncrads9 frame\n")
    assert request["msg_type"] == "xpaget"
    assert request["target"] == "ncrads9"
    assert request["command"] == "frame"
    assert request["params"] == {}


def test_parse_xpaset_with_payload():
    protocol = XPAProtocol()
    request = protocol.parse_request(
        b"xpaset -p ncrads9 regions\ncircle(10,20,5)\n"
    )
    assert request["msg_type"] == "xpaset"
    assert request["target"] == "ncrads9"
    assert request["command"] == "regions"
    assert request["params"]["data"] == "circle(10,20,5)"


def test_parse_plain_command_with_args():
    protocol = XPAProtocol()
    request = protocol.parse_request(b"frame 3\n")
    assert request["command"] == "frame"
    assert request["params"]["value"] == 3
    assert request["params"]["args"] == [3]


def test_format_response_handles_structured_values():
    protocol = XPAProtocol()
    response = protocol.format_response({"status": "ok", "result": {"mode": "fit"}})
    assert response.decode("utf-8").strip() == '{"mode": "fit"}'
