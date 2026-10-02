import base64
import io
import json
import subprocess
import urllib.error
import urllib.request
import zipfile

BASE = "http://127.0.0.1:18090"

def bundle() -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("openvpn.ovpn", "client\nremote 127.0.0.1 443\ndev tun\nproto udp\nauth-user-pass\nscript-security 2\nca ca.crt\ncert client.crt\nkey client.key\nremote-cert-tls server\n")
        z.writestr("ca.crt", "-----BEGIN CERTIFICATE-----\nTEST-CA\n-----END CERTIFICATE-----\n")
        z.writestr("client.crt", "-----BEGIN CERTIFICATE-----\nTEST-CLIENT\n-----END CERTIFICATE-----\n")
        z.writestr("client.key", "-----BEGIN PRIVATE KEY-----\nTEST-KEY\n-----END PRIVATE KEY-----\n")
    return base64.b64encode(buf.getvalue()).decode()

def call(path: str, method: str = "GET", payload=None, expected=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = json.load(response)
            if expected is not None:
                assert response.status == expected, (response.status, body)
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode() or "{}")
        if expected is not None:
            assert exc.code == expected, (exc.code, body)
            return exc.code, body
        raise

common = {
    "country": "Testland",
    "transport": "auto",
    "username": "vpn-test-user",
    "password": "vpn-test-password",
    "pre_shared": "CyberGhost",
    "bundle_base64": bundle(),
    "bundle_filename": "cyberghost-test.zip",
    "firewall_outbound_subnets": "192.168.0.0/16,172.30.0.0/24",
    "features": {
        "malicious_websites": True,
        "block_ads": True,
        "block_tracking": False,
        "redirect_https": False,
    },
}

_, first = call("/api/vpn/profiles", "POST", {**common, "name": "Primary", "server_group": "127.0.0.1", "startup_enabled": True}, 201)
first_id = first["profile"]["id"]
serialized = json.dumps(first)
assert "vpn-test-user" not in serialized
assert "vpn-test-password" not in serialized
assert "TEST-KEY" not in serialized

_, listing = call("/api/vpn/profiles")
assert listing["startupProfileId"] == first_id
assert len(listing["profiles"]) == 1

_, activated = call(f"/api/vpn/profiles/{first_id}/activate", "POST", None, 202)
assert activated["started"] is False
_, status = call("/api/vpn/status")
assert status["deploymentMode"] == "direct"
assert status["activeProfileId"] == first_id

profile_dir = "/vpn/profiles/" + first_id
check = (
    f"grep -q 'remote 127.0.0.1 443' {profile_dir}/openvpn.runtime.ovpn && "
    f"grep -q 'ca {profile_dir}/ca.crt' {profile_dir}/openvpn.runtime.ovpn && "
    f"! grep -q '^script-security' {profile_dir}/openvpn.runtime.ovpn"
)
subprocess.run(["docker", "exec", "webadmin-vpn-smoke", "sh", "-c", check], check=True)

call(f"/api/vpn/profiles/{first_id}", "DELETE", None, 409)
_, second = call("/api/vpn/profiles", "POST", {**common, "name": "Secondary", "server_group": "127.0.0.1", "startup_enabled": False}, 201)
second_id = second["profile"]["id"]
call(f"/api/vpn/profiles/{second_id}/activate", "POST", None, 202)
call(f"/api/vpn/profiles/{first_id}/startup", "PUT", {"enabled": False}, 200)
call(f"/api/vpn/profiles/{first_id}", "DELETE", None, 200)
_, final = call("/api/vpn/profiles")
assert len(final["profiles"]) == 1
assert final["profiles"][0]["id"] == second_id
