from stremiosrv.torrent.auto_port import desired_port, flag_enabled, vpn_provider

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


def test_provider_policy(tmp_path):
 import json
 root=tmp_path
 (root/'enabled').write_text('true')
 (root/'active_profile').write_text('cyberghost-test')
 folder=root/'profiles'/'cyberghost-test'
 folder.mkdir(parents=True)
 (folder/'profile.json').write_text(json.dumps({'provider':'cyberghost','protocol':'openvpn'}))
 assert vpn_provider(str(root/'enabled'))=='cyberghost'
 (folder/'profile.json').write_text(json.dumps({'provider':'proton','protocol':'wireguard'}))
 assert vpn_provider(str(root/'enabled'))=='proton'
 (root/'enabled').write_text('false')
 assert vpn_provider(str(root/'enabled'))==''


def test_proton_port_change_and_expired_lease(tmp_path):
    path = tmp_path / 'forwarded_port'
    path.write_text('36131\n')
    assert desired_port(6881, str(path), True) == (36131, 'vpn-forwarded')
    path.write_text('38427\n')
    assert desired_port(6881, str(path), True) == (38427, 'vpn-forwarded')
    path.unlink()
    assert desired_port(6881, str(path), True) == (6881, 'vpn-no-forwarding')
