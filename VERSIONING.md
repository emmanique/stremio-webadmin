# Versioning policy

## Fork release and upstream version

The project tracks two independent version lines:

```text
FORK_VERSION                 fork/platform release (2.x)
webadmin/WEBADMIN_VERSION    WebAdmin release (2.x)
SERVER_VERSION               integrated upstream server baseline
pyproject.toml               upstream stremiosrv package version
```

Current baseline:

```text
Fork/Platform    2.0.18
WebAdmin         2.0.18
VPN Gateway      2.0.18
Upstream Server  1.6.15
```

The fork release tag is `vX.Y.Z`. Container images are tagged with the fork release version. Server/core reporting remains tied to the independently integrated upstream version.

## Release contract

- `FORK_VERSION` equals `webadmin/WEBADMIN_VERSION` and the requested 2.x release tag.
- `SERVER_VERSION` equals the version in `pyproject.toml`.
- Updating the fork/WebAdmin version does not implicitly rewrite the upstream/core version.
- `.github/UPSTREAM_BASE` records the exact integrated upstream commit.
- `README.md`, `QUICKSTART.md`, `.env.example` and `docs/releases/vX.Y.Z.md` must describe installation/upgrade impact before a release can pass Full regression.

## Release source

Production packages and `:latest` image aliases are published only from a validated release commit on `main`. Feature/development branches never publish production aliases.

## Branch mapping

Only `main` and `development` are long-lived. Release, hotfix, feature and fix branches are temporary. See `docs/BRANCHING.md`.
