# Component Versioning and Release Policy

This fork has three independent version references. They must not be treated as one release number.

## 1. Streaming Server release

Authoritative file: `SERVER_VERSION`

This version changes when the Stremio server image changes: core integration, runtime wrapper, server Dockerfile, server-side configuration behaviour, migration/update logic that changes the server image, or another server-runtime change.

`FORK_VERSION` is retained as a compatibility alias and must always contain exactly the same value as `SERVER_VERSION`.

The WebAdmin server-update button compares the installed `/srv/app/SERVER_VERSION` with the remote `SERVER_VERSION`. When a newer version exists, WebAdmin pulls the matching immutable package from:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:<SERVER_VERSION>
```

Activation is transactional: the current image is retained as rollback, only the Stremio container is replaced, health is validated, and the previous container is restored automatically if activation fails. WebAdmin and Pi-hole are not recreated.

## 2. WebAdmin release

Authoritative file: `webadmin/WEBADMIN_VERSION`

This version changes when the WebAdmin API, UI, logging, administration functions, version lifecycle layer, or WebAdmin container changes.

WebAdmin is published independently as:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:<WEBADMIN_VERSION>
```

A WebAdmin release does not rebuild the streaming server. Host-side activation is:

```bash
docker compose pull webadmin
docker compose up -d --no-deps webadmin
```

Persistent WebAdmin state and the shared configuration volume are preserved.

## 3. Core version

Source: the `stremiosrv` package version reported by `/health`.

The core version is informational. It identifies the upstream-derived server core included in the fork, but it is not the runtime update authority. Updates are always released through this fork.

## Default deployment model

The stable `compose.yaml` is package-only. It pulls Server, WebAdmin and Pi-hole images and does not require local application builds.

The default stable aliases are:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:latest
pihole/pihole:latest
```

`start.sh` detects the host IPv4 and, by default, runs `docker compose pull` followed by `docker compose up -d`.

## Development and release flow

All normal development occurs first on the permanent `future` branch. The complete validation gate must pass before promotion to `main`.

`main` is the stable branch. A GitHub release tag uses:

```text
v<SERVER_VERSION>
```

The release workflow builds and smoke-tests both Server and WebAdmin, publishes their versioned and `latest` GHCR tags, then creates or refreshes the GitHub Release.

## Release rules

- Server-only change: bump `SERVER_VERSION` and copy the same value to `FORK_VERSION`.
- WebAdmin-only change: bump `webadmin/WEBADMIN_VERSION` only.
- Change affecting both components: bump both independent versions.
- Upstream synchronization alone does not create a production release until the relevant fork version is deliberately bumped and validated.
- `SERVER_VERSION`/`FORK_VERSION`, WebAdmin files, Compose files and release workflows are protected from automatic upstream replacement.
- Runtime updates never pull or build directly from the upstream repository.

The Fork Integration Guard verifies these invariants on every pull request and push to `main`.
