# Versioning policy

## 2.x unified versioning

Starting with 2.0.0, the platform uses one release version across all first-party components:

```text
SERVER_VERSION
FORK_VERSION
webadmin/WEBADMIN_VERSION
pyproject.toml
```

For an official release, all four values must be identical.

Example:

```text
2.0.0
```

The release tag is:

```text
v2.0.0
```

Published package tags include:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:2.0.0
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:2.0.0
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:2.0.0
```

The moving aliases `:2` and `:latest` are updated only by the validated 2.x release workflow.

## Semantic versioning

2.x follows semantic versioning:

- MAJOR: incompatible deployment, configuration or API changes.
- MINOR: backwards-compatible functionality.
- PATCH: backwards-compatible corrections.

## Release source

Production packages must be built from a validated `v2.x.y` tag. Feature and development branches never publish `:latest`.

## Branch mapping

See `docs/BRANCHING-2X.md`.

## Legacy 1.x

The old split component numbering remains historical. The legacy release workflow is restricted to 1.x tags so it cannot publish a 2.x release.
