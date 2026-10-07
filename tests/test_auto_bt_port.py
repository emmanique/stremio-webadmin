from stremiosrv.torrent.auto_port import desired_port, flag_enabled

def test_direct_ignores_stale_forward(tmp_path):
 p=tmp_path/"forwarded_port"; p.write_text("45678\n"); assert desired_port(6881,str(p),False)==(6881,"direct")
def test_vpn_without_forwarding(tmp_path):
 assert desired_port(6881,str(tmp_path/"missing"),True)==(6881,"vpn-no-forwarding")
def test_vpn_forwarded_port(tmp_path):
 p=tmp_path/"forwarded_port"; p.write_text("45678\n"); assert desired_port(6881,str(p),True)==(45678,"vpn-forwarded")
def test_invalid_forwarded_port_falls_back_inside_vpn(tmp_path):
 p=tmp_path/"forwarded_port"; p.write_text("99999\n"); assert desired_port(6881,str(p),True)==(6881,"vpn-no-forwarding")
def test_vpn_flag(tmp_path):
 p=tmp_path/"enabled"; p.write_text("true\n"); assert flag_enabled(str(p)); p.write_text("false\n"); assert not flag_enabled(str(p))
