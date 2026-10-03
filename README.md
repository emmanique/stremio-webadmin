# Stremio Server WebAdmin 3.0.8


Self-hosted Stremio streaming platform with Stremio/libtorrent server, WebAdmin, Pi-hole, optional Gluetun/OpenVPN routing and hardware transcoding support.

Current versions:

| Component | Version |
| --- | --- |
| Fork / Platform | 3.0.8 |
| WebAdmin | 3.0.8 |
| VPN Gateway image | `3.0.6` coordinated release tag |
| Upstream Server/Core | 1.6.23 |

## 3.0.8 — Web Player persistence and host disk protection

Version 3.0.8 integrates the Server/Core 1.6.23 Web Player loader correction
while preserving the fork-owned WebAdmin, VPN, Library and transcoding
architecture.

A streaming-server URL selected manually in the Web Player is now preserved
instead of being periodically overwritten by the deployment seed URL.

Ordinary Library downloads now also enforce a host filesystem reserve before
adding a torrent. The default reserve is the greater of 10 GiB or 10% of the
filesystem, while retaining the lower upstream operational safety floor.
Committed download bytes and the requested candidate size are included in the
admission decision. The existing stricter Keep/Pin policy remains independent
and unchanged.

The new deployment settings are:

- `STREMIOSRV_HOST_MIN_FREE_GB=10`
- `STREMIOSRV_HOST_MIN_FREE_PERCENT=10`

The VPN Gateway remains unchanged at the previously validated 3.0.6 image.

See `docs/releases/v3.0.8.md` for validation and upgrade details.

## 3.0.7 — Web Player playback corrections

Version 3.0.7 is a corrective release for browser playback while retaining
Server/Core 1.6.22 and the distribution architecture introduced in 3.0.6.

The release provides a deterministic single-track HLS master while preserving
the fMP4 media path, supports Stremio's implicit `fileIdx=-1` throughout the
HLS/WebVTT subtitle path, and corrects WebAdmin playback classification when
the playback registry contains no correlated entry.

The VPN Gateway is unchanged from 3.0.6.

## 3.0.6 — Public distribution architecture

Version 3.0.6 introduces the separated private-development and public-distribution release model.

Official stable container images:

- `ghcr.io/emmanique/stremio-server:3.0.6`
- `ghcr.io/emmanique/stremio-webadmin:3.0.6`
- `ghcr.io/emmanique/stremio-vpn:3.0.6`

The Stremio Server/Core remains at version 1.6.22.

## 3.0.5 — Upstream 1.6.22 integration and proxy hardening

3.0.5 selectively integrates the functional fixes from upstream Server/Core 1.6.22
without replacing the fork's custom WebAdmin, VPN, Library, proxy or transcoding
behavior. The existing UPnP configuration now reaches libtorrent; disabling it also
disables NAT-PMP port mapping while leaving DHT/LSD unchanged.

Playlist handling now rejects responses that terminate before their declared
Content-Length. The protection applies to both the normal proxy playlist path and
the guarded external `mediaURL` reader used by HLS/transcoding.

The DEV release candidate passed VPN/DIRECT switching, proxy/HLS, real
HDR-to-SDR VAAPI playback, My Library Pin/Unpin, external `mediaURL` probe/HLS,
and configuration SAVE + RESTART/persistence validation.

Upgrade/recreate operations on GPU hosts must continue to use `start.sh` so the
appropriate VAAPI/NVIDIA Compose overlay is retained.

See `docs/releases/v3.0.5.md` for the complete scope, validation and upgrade notes.

## 3.0.4 — Playback continuity and runtime observability

3.0.4 consolidates the playback work validated on the DEV platform: authoritative
playback-session telemetry, improved WebAdmin direct-stream/transcode correlation,
safer FFmpeg policy handling, and Continue Watching source continuity.

For Continue Watching, the centre Play action now follows Stremio Core's existing
player deep link when available, preserving the exact prior stream and Core-managed
resume position. Poster/details navigation remains unchanged so users can still open
the normal source picker when they want another source.

The Library Addon records the last successfully observed source and prefers it when
presenting matching local streams. The release does not create a second progress
database: Stremio Core remains authoritative for playback position.

Upgrade/recreate operations on GPU hosts must be run through `start.sh`; the launcher
automatically selects the VAAPI/NVIDIA Compose overlay. Plain `docker compose up
--force-recreate` can omit the GPU device mapping.

See `docs/releases/v3.0.4.md` for validation and upgrade notes.

## 3.0.3 — Pi-hole DNS path enforcement

3.0.3 makes Pi-hole the normal resolver for Stremio, libtorrent and child
processes in both DIRECT and VPN modes. Stremio uses a private
`/etc/resolv.conf` pointing to `172.30.0.53`; Pi-hole forwards through
Gluetun's private DNS proxy on `172.30.0.10:1053`.

WebAdmin validation now proves the end-to-end path
Stremio -> Pi-hole -> Gluetun:1053 and applies VPN-only checks only while
VPN mode is requested. The deployment ZIP/TAR includes the resolver file.

See `docs/releases/v3.0.3.md` for validation and upgrade notes.

## 3.0.2 — HDR/Dolby Vision VAAPI fix

3.0.2 fixes the validated HDR/PQ and Dolby Vision Profile 8
browser/HLS server-transcoding path.

When AUTO has already selected server video transcoding, detected source
colour metadata is supplied explicitly to FFmpeg and the validated path
uses VAAPI decode, `tonemap_vaapi`, optional `scale_vaapi`, and H.264
VAAPI encode.

Direct/COPY playback remains independent and is not promoted to
transcoding by the VAAPI execution policy.

See `docs/releases/v3.0.2.md` for validation evidence and scope.

## 3.0.1 — Intel VAAPI hotfix

- Canonicalizes `LIBVA_DRIVER_NAME=ihd` to the case-sensitive Intel Media Driver name `iHD` before Compose is invoked.
- Prevents inherited or legacy lowercase overrides from making libva search for the non-existent `ihd_drv_video.so` instead of `iHD_drv_video.so`.
- Keeps `LIBVA_DRIVER_NAME` optional: an empty value still allows libva autodetection.
- Validated on Intel Iris Xe with `/dev/dri/renderD128`: `vainfo` opens the iHD driver and real FFmpeg H.264/HEVC VAAPI encode tests pass.
- Upgrade from 3.0.0 preserves `.env` and all named volumes; production images should be pinned to the coordinated `3.0.1` tags after publication.

## 3.0.0 — features added by this fork

Version 3.0.0 marks the platform-level fork as a distinct distribution rather than only a repackaged upstream server. The upstream/core version remains independently versioned; the capabilities below are maintained by this fork on top of the main upstream server.

### WebAdmin and operations

- Independent **WebAdmin** service that remains available while the Stremio server container is restarted or recreated.
- Browser dashboard for runtime health, component versions, configuration, restart operations, logs, cache/stream visibility and transcoding diagnostics.
- Persistent WebAdmin/server configuration outside the application containers so normal image replacement does not discard local settings.
- Configuration save/read-back and server restart flows designed to survive DIRECT/VPN deployment changes.
- Release validation confirmed configuration persistence in `/config/admin-settings.json`, a real server restart (`StartedAt` changed), persistence after restart, and restoration of the original value.

### Integrated network stack

- Single Compose-based platform integrating **Stremio Server, WebAdmin, Pi-hole and Gluetun**.
- VPN can remain unconfigured/disabled without preventing normal DIRECT operation; enabling it switches the streaming stack to VPN egress.
- Pi-hole is integrated as the platform DNS layer, with optional LAN DNS exposure rather than requiring host port 53 in the base deployment.
- Stable Gluetun network namespace and fail-closed behaviour while VPN operation is explicitly requested.
- Release validation confirmed VPN -> DIRECT -> VPN switching with the Stremio server remaining healthy, Pi-hole/DNS resolution working in both modes, and the final VPN state restoring tunnel routing, kill-switch and fail-closed protection.
- Host-neutral deployment variables, automatic host-IP discovery and explicit overrides for multi-homed/special installations.

### Automatic GPU transcoding

- **AUTO-only transcoding policy**: WebAdmin detects and exposes acceleration but does not manually choose the playback codec or force a transcode.
- Automatic Intel/DRM **VAAPI** and NVIDIA/**NVENC** capability discovery, with CPU-safe operation when no validated accelerator is available.
- Real FFmpeg capability checks distinguish GPU detection, runtime readiness and usable H.264/HEVC encode capability.
- Live telemetry distinguishes an available GPU from the engine actually used by current playback; Direct Stream/copy remains visible as copy.
- Equivalent HLS workloads are deduplicated so compatible clients share one main video FFmpeg/HLS job instead of unnecessarily creating duplicate video transcodes.
- Transcode lifecycle/garbage collection is hardened against workload cleanup races.

### HDR-aware playback

- Probe metadata retains video profile, pixel format, bit depth, colour transfer/primaries, HDR and Dolby Vision indicators.
- HDR10/PQ/HLG can follow the validated AUTO VAAPI HDR-to-SDR path when transcoding is required: hardware decode, `tonemap_vaapi`, BT.709 output and `h264_vaapi` encode.
- HEVC SDR remains eligible for Direct Stream/copy when compatible.
- Dolby Vision is deliberately kept separate from the HDR10 fallback until a DoVi-specific path is validated instead of silently treating DoVi as HDR10.

### Embedded subtitles for browser/HLS playback

- Embedded subtitle tracks are discovered and advertised as HLS subtitle renditions without mixing subtitle extraction into the main video FFmpeg process.
- WebVTT is delivered in finite 30-second HLS windows rather than one movie-length streaming subtitle response.
- Window extraction uses output-side seeking to avoid header-only WebVTT results observed with sparse embedded subtitle streams.
- Each window carries `X-TIMESTAMP-MAP` so FFmpeg segment-local cue times are mapped to the HLS playback clock.
- This finite-window + timestamp-map path has been validated in real browser playback with visible, synchronized and continuous subtitles.
- Subtitle-only FFmpeg extraction is excluded from the WebAdmin count of active video transcodes.

### Streaming/proxy compatibility and resilience

- Dedicated media-fetch/proxy handling, upstream playlist/client compatibility work, handshake compatibility and library/protocol adaptations support the self-hosted browser stack.
- Torrent/media destination guards remain in the fetch path; subtitle and HLS changes do not bypass existing media-input validation.
- Pins/library behaviour and browser compatibility have dedicated regression coverage.

### Deployment and regression engineering

- Minimal release deployment packages are supported so a production host does not require a complete source checkout.
- Upgrade guidance preserves `.env`, configuration/state volumes, VPN material and persistent data.
- CI separates fast checks, dependency checks and full regression, including deployment/package validation.
- Expanded regression coverage includes AUTO GPU routing, HDR decisions, HLS/subtitles, deduplication/GC, proxy/media fetch, handshake, pins/library, Compose topology and WebAdmin transcoding detection.

> **Versioning note:** `3.0.0` is the version of this fork/platform and WebAdmin. The embedded Stremio server/core keeps its own upstream-derived version (currently `1.6.20`) so fork features are not misrepresented as upstream features.

## What changed in 3.0.0

### Automatic transcoding architecture

- Transcoding execution is now **AUTO-only**. WebAdmin no longer selects or forces H.264, HEVC, VAAPI, NVENC, CPU or a manual execution profile.
- The Stremio core remains authoritative for the media decision: **Direct Stream/copy vs transcode and the required output codec**. Detecting a GPU never forces re-encoding.
- `GPU_BACKEND=auto` discovers a usable VAAPI or NVIDIA/NVENC backend and exposes that capability to the runtime. If no valid GPU backend exists, the server remains on the normal Stremio/CPU path.
- Intel/DRM installations discover the available render node instead of assuming `/dev/dri/renderD128`. `VAAPI_DEVICE` may still be set explicitly for a validated host-specific override.
- `LIBVA_DRIVER_NAME` is optional. Leave it empty for libva autodetection; set a driver such as `iHD` only when the host requires it.
- WebAdmin hardware tests for H.264/HEVC are **diagnostic capability tests only**. They do not choose the playback codec and do not mean that an idle or copy session is using the encoder.
- Live WebAdmin telemetry reports AUTO policy, detected backend/device, active FFmpeg sessions, actual Direct Stream/transcode state and the effective runtime decision.
- Legacy profile/codec fields are retained only for upgrade compatibility and diagnostics; they are no longer authoritative execution controls and are read-only in the configuration UI.
- Equivalent HLS requests are deduplicated by effective workload so compatible requests share one main video FFmpeg/HLS job. Subtitle extraction remains an independent process and is not treated as a duplicate video transcode.
- Embedded WebVTT subtitles are advertised as HLS subtitle renditions using finite 30-second media windows. Each window is extracted independently from the source track, avoiding both the former movie-length streaming segment and the invalid URI-only rendition while preserving the independent subtitle extractor.
- Transcode lifecycle/garbage collection was hardened to avoid workload cleanup races.
- Media probing preserves HDR-relevant video metadata (`profile`, pixel format/bit depth, transfer and primaries) in addition to `isHdr`/`isDoVi`. Because the current HLS client contract has no HDR display-capability signal, normal HDR10/PQ/HLG sources now use the validated conservative HDR-to-SDR transcode fallback; Dolby Vision remains separate and is not silently treated as HDR10.

### Deployment, upgrade and CI

- Production installation is now based on a minimal deployment ZIP/TAR attached to a GitHub Release, not a full source checkout.
- The deployment baseline is host-neutral: no fixed LAN IP, personal allowlist, Angola-only timezone or mandatory GPU device.
- start.sh reads local .env values safely and keeps precedence as exported environment > .env > autodetection/default.
- GPU_BACKEND=auto selects VAAPI or NVIDIA only after local runtime capability is detected; otherwise it remains CPU-safe.
- A pre-upgrade backup script preserves configuration/state volumes and records the resolved Compose/image state.
- CI is separated into Fast CI, Dependencies, Full regression, Prepare release, Release and Upstream sync.
- Full regression builds and validates the deployment package and simulates a clean installation from it before a production release.
- The 3.0.0 release-candidate baseline completed 1,356 deterministic tests passed (9 skipped, 10 deselected) plus 8 integration tests passed (2 skipped, 1,365 deselected), followed by successful server/WebAdmin/VPN image builds, deployment archive validation and SHA-256 verification.
- Only main and development are long-lived branches. feature/*, fix/*, release/* and hotfix/* are temporary.

## Hardware compatibility notes

- GPU auto-detection now treats hardware exposure and the active transcoding profile as separate concerns.
- Dual-GPU hosts can expose both Intel/DRM VAAPI and NVIDIA to the server container when both runtimes are available; WebAdmin still enables only profiles that pass real FFmpeg self-tests.
- VAAPI no longer assumes `/dev/dri/renderD128`. `start.sh` discovers an available render node and exports `VAAPI_DEVICE`; WebAdmin then verifies real FFmpeg capability inside the server container; direct Compose usage with `compose.vaapi.yaml` must provide `VAAPI_DEVICE` explicitly.
- An empty `LIBVA_DRIVER_NAME` is no longer forced into the server container, allowing libva driver autodetection. Set an explicit value such as `iHD` only when the host requires it.
- NVIDIA detection, container-runtime readiness and NVENC encoder compatibility are reported separately. Legacy GPUs can therefore be shown as detected/runtime-ready even when their driver exposes an older NVENC API than the bundled FFmpeg requires.
- Upgrade impact: existing `.env` files remain valid. Review `VAAPI_DEVICE` and `LIBVA_DRIVER_NAME` only if they were previously set as host-specific overrides.

## Runtime architecture

~~~text
Host / LAN
  |
  +-- WebAdmin :8090
  +-- Pi-hole  :8053
  +-- Gluetun gateway/network namespace
        |
        +-- Stremio Server :8080 / :11470 / :12470 / :6881
        +-- DIRECT egress when VPN is disabled
        +-- VPN egress when enabled
~~~

The Gluetun container remains present as the stable network namespace. Disabling VPN stops the tunnel, not the container.

# New installation

## 1. Requirements

- Linux host with Docker Engine and Docker Compose plugin.
- curl or wget and tar/unzip.
- A writable installation directory such as /opt/stremio-webadmin.
- Ports 8080, 8090, 11470, 12470 and 6881 TCP/UDP available on the selected host IP.
- Port 8053 for Pi-hole Web. Host DNS port 53 is optional and only used with compose.dns.yaml.

Verify Docker first:

~~~bash
docker --version
docker compose version
~~~

## 2. Obtain the deployment package

For production, use the deployment ZIP or TAR.GZ attached to the desired GitHub Release. Do not clone the complete repository on a normal production host.

Example using a released TAR.GZ:

~~~bash
VERSION=3.0.2
INSTALL_DIR=/opt/stremio-webadmin

sudo mkdir -p "$INSTALL_DIR"
curl -fL \
  -o "/tmp/stremio-webadmin-${VERSION}-deployment.tar.gz" \
  "https://github.com/emmanique/stremio-webadmin/releases/download/v${VERSION}/stremio-webadmin-${VERSION}-deployment.tar.gz"

sudo tar -xzf "/tmp/stremio-webadmin-${VERSION}-deployment.tar.gz" \
  -C "$INSTALL_DIR" --strip-components=1

cd "$INSTALL_DIR"
~~~

For an unreleased release candidate, use the deployment artifact produced by the Full regression workflow. Do not treat an unreleased main commit as a published production package.

## 3. Create the local configuration

~~~bash
cp .env.example .env
~~~

The .env file is installation state and must never be committed or replaced by an upgrade.

Review these parameters before first start:

| Variable | Action on a new installation |
| --- | --- |
| TZ | Set the local IANA timezone, for example Europe/Lisbon or Africa/Luanda. |
| PIHOLE_PASSWORD | Set a unique Pi-hole administrator password. |
| IPADDRESS_SOURCE | Keep auto normally. Use manual only when the host has multiple interfaces or autodetection is not appropriate. |
| IPADDRESS | Leave empty with auto. Set the exact host IPv4 when IPADDRESS_SOURCE=manual. |
| VPN_LAN_CIDRS | Change when the LAN is not covered by 192.168.0.0/16; include only trusted LAN subnets plus the platform internal subnet. |
| STREMIO_DIRECT_DNS_UPSTREAM | Change only if another resolver is required in DIRECT mode. |
| STREMIO_IMAGE / WEBADMIN_IMAGE / VPN_IMAGE | `latest` is convenient for development. For production, pin the published release tags. The VPN image used during final 3.0.0 runtime validation was `:latest`; do not assume a versioned VPN tag exists until the release workflow has published it. |
| SERVER_URL | Optional. Set when an explicit trusted Stremio HTTPS endpoint is required. |
| STREMIOSRV_LIBRARY_OWNER | Optional Stremio account `_id` or email. When empty, My Library is auto-installed for each account authenticated in the bundled Web Player; when set, auto-install is restricted to this account only. |
| STREMIOSRV_LIBRARY_ADDON_ALLOW | Leave empty for the built-in private-network allowlist unless a deliberate custom allowlist is required. |
| GPU_BACKEND | Keep auto for normal installations. |
| VAAPI_DEVICE | Leave empty unless a specific local render node has been validated. |
| LIBVA_DRIVER_NAME | Leave empty unless the host requires an explicit driver such as iHD. |

VPN credentials, certificates and private keys are not entered in .env. Configure/import them later in WebAdmin -> VPN.

## 4. Validate before starting

~~~bash
sh start.sh config
~~~

Do not continue if Compose reports an unresolved variable, invalid bind address, unavailable port or invalid topology.

## 5. Start

~~~bash
sh start.sh
~~~

With no arguments the launcher pulls the configured images and starts/reconciles the stack.

Typical access points, using the IP printed by start.sh:

| Service | URL / Port |
| --- | --- |
| Web Player | http://HOST-IP:8080 |
| WebAdmin | http://HOST-IP:8090 |
| Streaming API | http://HOST-IP:11470 |
| Trusted HTTPS / Library | https://HOST-IP:12470 |
| Pi-hole Web | http://HOST-IP:8053/admin/ |
| BitTorrent | 6881/tcp and 6881/udp |

## 6. First-install validation

~~~bash
sh start.sh ps
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
curl -fsS http://HOST-IP:11470/health
curl -fsS http://HOST-IP:8090/health
curl -fsS http://HOST-IP:8090/api/component-versions
~~~

Then verify in WebAdmin:

- configuration save and read-back;
- Server restart;
- Pi-hole state;
- VPN remains NOT CONFIGURED / DIRECT until explicitly configured;
- AUTO transcoding status, detected backend/device and capability diagnostics;
- Library access if enabled.

# Configuration rules

## IP addressing

With IPADDRESS_SOURCE=auto, start.sh detects the IPv4 used by the default route and refreshes the local .env when the host address changes. On multi-homed hosts use manual mode instead of relying on an arbitrary interface choice.

## GPU / transcoding

The execution policy is **AUTO-only**. Compatible streams are not re-encoded merely because a GPU exists. Stremio first decides whether video is copied or transcoded and which codec is required; hardware discovery only determines whether an available accelerator can implement a transcode that Stremio has already requested.

Recommended baseline:

~~~env
GPU_BACKEND=auto
VAAPI_DEVICE=
# LIBVA_DRIVER_NAME=iHD  # optional explicit override
TRANSCODING_HWACCEL=auto
TRANSCODING_MODE=auto
~~~

Do not configure `TRANSCODING_VIDEO_CODEC` to force H.264/HEVC as part of the AUTO baseline. Existing legacy codec/profile values may still be read during upgrade, but they are not authoritative execution decisions.

`start.sh` adds the VAAPI or NVIDIA overlay only when the local host can support it. Explicit GPU values are host-specific overrides.

Useful runtime checks:

~~~bash
curl -fsS http://HOST-IP:11470/transcode.json | python3 -m json.tool
curl -fsS http://HOST-IP:8090/api/transcoding/status | python3 -m json.tool
~~~

A detected backend such as `vaapi` means acceleration is available; it does **not** mean the current playback must use the GPU. A session whose actual FFmpeg command contains `-c:v copy` is correctly copying video even when VAAPI/NVENC is available.

Because the current HLS client contract does not explicitly declare HDR display capability, normal HDR10/PQ/HLG is conservatively marked for video transcode even when HEVC itself is declared supported. HEVC SDR remains COPY when otherwise compatible. In AUTO+VAAPI, HDR video transcode keeps decode, tone mapping and encode on the GPU, converting to SDR BT.709 through `tonemap_vaapi` and `h264_vaapi`. Intel Iris Xe runtime validation with a real 3840x1606 HEVC 10-bit BT.2020/PQ source produced HLS/fMP4 at about 1.56x realtime (20 seconds in 13 seconds), with H.264/yuv420p BT.709 output. The same source subsequently passed real Stremio playback through the normal HDR fingerprint -> AUTO VAAPI -> `tonemap_vaapi` -> `h264_vaapi` path. Dolby Vision is deliberately excluded from this HDR10 fallback until a DoVi-specific path is validated. The slower software `zscale + tonemap` path is not selected as the realtime AUTO path.

## VPN

Configure VPN from WebAdmin -> VPN. A new installation does not require VPN credentials.

State model:

~~~text
NOT CONFIGURED -> DIRECT
CONFIGURED/OFF  -> DIRECT
CONFIGURED/ON   -> VPN
VPN failure     -> fail-closed while VPN is requested
~~~

## Pi-hole DNS

The base stack does not expose host DNS port 53. To expose Pi-hole DNS to the LAN, first ensure the selected host IP has port 53 available and then use compose.dns.yaml.

# Upgrade

Upgrades must preserve the local .env and named Docker volumes.

## 1. Backup before every upgrade

~~~bash
cd /opt/stremio-webadmin
sh scripts/backup-before-upgrade.sh
~~~

Use --with-cache only when the large cache volume must also be archived:

~~~bash
sh scripts/backup-before-upgrade.sh --with-cache
~~~

The normal backup set includes configuration/state volumes such as stremio-config, webadmin-data, vpn-data, gluetun-data, pihole-etc and pihole-dnsmasq plus deployment metadata.

Never use docker compose down -v for a routine upgrade or rollback.

## 2. Preserve local configuration

Do not delete or overwrite:

- .env
- named Docker volumes;
- imported VPN material stored in persistent volumes;
- persistent certificate/cache data unless intentionally rebuilding it.

## 3. Replace deployment files

Download the new deployment package and extract it over the existing installation directory. The package intentionally does not contain .env.

## 4. Reconcile new variables

After extracting the new version, check which variables exist in the new template but are absent from the local .env:

~~~bash
sh scripts/check-env-upgrade.sh
~~~

The script only reports missing/obsolete variable names; it does not rewrite the local .env. Review each new variable and add it manually only when its default/behaviour is understood.

For a raw comparison you can also use:

~~~bash
diff -u .env .env.example || true
~~~

## 5. Validate and upgrade

~~~bash
sh start.sh config
sh start.sh pull
sh start.sh up -d --force-recreate
~~~

## 6. Post-upgrade validation

~~~bash
sh start.sh ps
curl -fsS http://HOST-IP:11470/health
curl -fsS http://HOST-IP:8090/health
curl -fsS http://HOST-IP:8090/api/component-versions
~~~

Also validate configuration save/restart, VPN state, DNS path, AUTO transcoding telemetry and detected hardware capability after each release upgrade.

# Rollback

Keep the backup created before the upgrade. Roll back deployment files/images to the previous coordinated release while preserving the persistent volumes. Do not remove volumes as part of a normal rollback.

If image variables are pinned, restore all coordinated component tags to the same prior platform release and run:

~~~bash
sh start.sh config
sh start.sh pull
sh start.sh up -d --force-recreate
~~~

# Development and branch model

Normal users do not need Git. Contributors use the source repository.

Long-lived branches:

- main: production/releasable state;
- development: integration for the next release.

Temporary branches:

- feature/<short-name> from development;
- fix/<short-name> from development;
- release/<x.y.z> from development and merged to main after full regression;
- hotfix/<short-name> from main and merged back/synchronised to development.

Do not create a permanent branch for each version. Historical branches such as develop/2.x are legacy references only and are not CI targets.

See docs/BRANCHING.md and docs/WORKFLOWS.md.

# CI / release gates

Fast CI: syntax, repository contracts, Compose validation, documentation contract and deterministic tests.

Dependencies: dependency graph, audits, dependency-sensitive tests and image builds.

Full regression: complete regression suite, integration tests, Server/WebAdmin/VPN builds and smoke tests, deployment-package generation and clean-install simulation.

Prepare release: creates the temporary release/<version> branch from development.

Release: publishes only from validated main, creates immutable version tags/images and attaches the deployment ZIP/TAR plus SHA256SUMS.

Upstream sync: isolates upstream changes in upstream/integration and proposes them to development; it never promotes directly to main.

# Repository vs deployment package

The source repository contains src/, webadmin/, vpn/, tests/, tools/, Actions and engineering documentation.

The production deployment package intentionally contains only the supported runtime surface: Compose files, launchers, .env.example, backup/upgrade helpers and operational documentation.

# Security notes

- Keep WebAdmin on a trusted LAN/VPN; it has Docker management access.
- Do not expose port 8090 directly to the public Internet.
- Do not commit .env, VPN credentials, private keys, certificates or Library tokens.
- Keep the VPN kill switch/fail-closed behaviour enabled.
- Treat explicit allowlists and LAN CIDRs as security boundaries, not convenience defaults.

# Release information

Release notes: docs/releases/v3.0.5.md

License: MIT. See LICENSE.

## 3.0.0 AUTO runtime validation

The launcher owns host discovery. Run `./start.sh --help` to inspect launcher usage without creating/updating `.env`, probing the host GPU, pulling images, or starting containers. With `GPU_BACKEND=auto`, `start.sh` discovers the available DRM render node (for example `/dev/dri/renderD128`) and exports it to the VAAPI Compose overlay for that invocation; users do not need to persist `VAAPI_DEVICE` in `.env`. Calling `docker compose -f compose.yaml -f compose.vaapi.yaml ...` directly bypasses launcher discovery and therefore requires `VAAPI_DEVICE` in that shell.

AUTO keeps playback policy separate from execution capability. If Stremio decides COPY, video remains `-c:v copy` even when VAAPI/NVENC is available. If Stremio decides video TRANSCODE, AUTO routes the existing H.264 transcode target through detected VAAPI encode, NVENC encode, or `libx264` when no supported GPU backend is available. GPU availability never promotes COPY to TRANSCODE and AUTO does not force hardware decode. Runtime validation on Intel Iris Xe also confirmed a real `h264_vaapi` encode and an end-to-end `Converter` transcode producing HLS/fMP4 with `master.m3u8`, `index.m3u8`, `init.mp4` and `.m4s` media segments. Validation tooling must accept `.m4s` for this HLS path rather than assuming MPEG-TS segments.


The transcoding capability API uses AUTO semantics: backend/encoder self-tests are diagnostic capability data, not selectable execution profiles. It exposes `detectedBackend` and `availableForAuto` rather than the legacy `recommendedProfile` / `selectable` contract.


Windowed HLS WebVTT responses include `X-TIMESTAMP-MAP`, mapping FFmpeg's segment-local cue timestamps onto the corresponding 90 kHz HLS playback timeline.

Subtitle HLS timing diagnostics are emitted only at debug log level; normal runtime logs remain quiet after validation.
