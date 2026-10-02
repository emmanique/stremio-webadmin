# Versioning policy

## Fork release and upstream version

Starting with fork 2.x, the project tracks two independent version lines:

```text
FORK_VERSION                 fork/platform release (2.x)
webadmin/WEBADMIN_VERSION    WebAdmin release (2.x)
SERVER_VERSION               andrewhack upstream server baseline
pyproject.toml               upstream stremiosrv package version
```

For release 2.0.3 the mapping is:

```text
Fork/Platform   2.0.3
WebAdmin        2.0.3
VPN Gateway     2.0.3
Upstream Server 1.6.14
```

The fork release tag remains `v2.0.3`. Container images are tagged with the fork release version. The server/core version shown by component/version reporting must reflect the upstream server version.

## Release contract

- `FORK_VERSION` must equal `webadmin/WEBADMIN_VERSION` and the requested 2.x release tag.
- `SERVER_VERSION` must equal the version in `pyproject.toml`.
- `SERVER_VERSION` follows the integrated andrewhack/stremio-libtorrent-server release and is not rewritten to the fork release number.
- `.github/UPSTREAM_BASE` records the exact integrated upstream commit.

## Semantic versioning

The fork 2.x release line follows semantic versioning independently of upstream.

## Release source

Production packages must be built from a validated `v2.x.y` fork tag. Feature and development branches never publish `:latest`.

## Branch mapping

See `docs/BRANCHING-2X.md`.
