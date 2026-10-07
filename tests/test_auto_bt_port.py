from stremiosrv.torrent.auto_port import desired_port

def test_auto_port_defaults_when_state_missing(tmp_path):
    assert desired_port(6881, str(tmp_path / "missing")) == (6881, "default")

def test_auto_port_uses_forwarded_port(tmp_path):
    p = tmp_path / "forwarded_port"; p.write_text("45678\n")
    assert desired_port(6881, str(p)) == (45678, "vpn-forwarded")

def test_auto_port_rejects_invalid_provider_state(tmp_path):
    p = tmp_path / "forwarded_port"; p.write_text("99999\n")
    assert desired_port(6881, str(p)) == (6881, "default")

def test_auto_port_empty_path_is_direct_default():
    assert desired_port(6881, "") == (6881, "direct")
