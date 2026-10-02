# Clean installation acceptance test

This procedure validates a deployment package as if the host had never run Stremio Server WebAdmin before.

## Preconditions

- Use a dedicated test host.
- Do not copy an existing .env, Docker volume or VPN profile into the new installation.
- Confirm Docker Engine and Docker Compose plugin are installed.
- Confirm the test host IP and that required ports are available.

## 1. Remove only the previous test installation

If this host is intentionally being reset for a clean-install test, remove the old stack and its project volumes only after confirming that no production data exists on the host.

Record the existing state before deletion:

~~~bash
docker ps -a
docker volume ls
docker network ls
~~~

Then use the cleanup procedure appropriate to the previous test deployment. A clean-install acceptance test must not inherit the previous .env or named project volumes.

## 2. Install from the release deployment package

Follow the New installation section in README.md exactly. Do not clone the source repository.

Expected before first start:

~~~text
.env does not exist until copied from .env.example
no existing stremio-* application volumes
no imported VPN profile
no host-specific GPU override
~~~

## 3. Configure only required local values

At minimum review TZ, PIHOLE_PASSWORD, LAN CIDRs and host IP mode. Keep GPU_BACKEND=auto and VAAPI_DEVICE empty for the first start unless the host requires a known explicit override.

## 4. Pre-start gate

~~~bash
sh scripts/check-env-upgrade.sh
sh start.sh config
~~~

PASS when:

- the env checker reports no missing template variables;
- Compose resolves without warnings/errors that indicate missing values;
- no personal IP, email, GPU node or timezone from another installation appears unexpectedly.

## 5. Start

~~~bash
sh start.sh
sh start.sh ps
~~~

PASS when the expected containers are running and Gluetun starts in DIRECT mode without requiring a VPN account.

## 6. API and WebAdmin health

Replace HOST-IP with the address printed by start.sh:

~~~bash
curl -fsS http://HOST-IP:11470/health
curl -fsS http://HOST-IP:8090/health
curl -fsS http://HOST-IP:8090/api/component-versions
~~~

PASS when Server and WebAdmin report healthy and the coordinated platform version is the version under test.

## 7. Persistence and restart regression

From WebAdmin, change one harmless configuration value, save it, restart the Server, then confirm the value remains after restart.

PASS when:

- save succeeds;
- /config/admin-settings.json remains persistent;
- Server restart completes;
- the saved value remains after restart.

## 8. VPN baseline

Without importing a VPN profile, confirm the WebAdmin reports VPN as not configured/disabled and Internet access uses DIRECT mode.

Then, if VPN testing is in scope, import a valid profile and validate DIRECT -> VPN -> DIRECT including DNS and fail-closed behaviour.

## 9. DNS / Pi-hole

Confirm Pi-hole Web is reachable. If LAN DNS exposure is required, test compose.dns.yaml separately after confirming host port 53 is free.

## 10. Transcoding

Refresh the transcoding capability matrix. On a generic host, CPU must remain available. Hardware profiles may only become selectable after their local runtime self-test succeeds.

Do not copy a VAAPI render node from another host.

## 11. Upgrade rehearsal

Before replacing the candidate with the next candidate/release:

~~~bash
sh scripts/backup-before-upgrade.sh
sh scripts/check-env-upgrade.sh
sh start.sh config
~~~

PASS when local .env and persistent volumes survive the upgrade and any newly introduced variables are explicitly identified before start.

## Acceptance result

Record PASS/FAIL for: package extraction, generic .env, Compose validation, container start, Server health, WebAdmin health, configuration persistence, restart, VPN baseline, DNS, transcoding and upgrade rehearsal.
