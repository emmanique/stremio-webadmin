# Repository workflows

The repository uses five permanent GitHub Actions workflows.

## 1. CI — `.github/workflows/ci.yml`

Purpose: protect all runtime functionality before code reaches a stable branch.

Runs automatically on pushes to:

- `main`;
- `develop/2.x`;
- `release/**`.

Feature, fix, hotfix and upstream-import branches are validated when opened as pull requests to `main` or `develop/2.x`. Documentation-only changes are ignored by CI.

Validation includes:

- coordinated component version contract;
- fork-owned runtime/update paths;
- Python, shell, JavaScript and PowerShell syntax;
- Windows launcher wrappers;
- base/DNS/VAAPI/NVIDIA Compose variants;
- deterministic pytest suite;
- network integration tests on `main`, release branches and manual runs;
- Server, WebAdmin and VPN image builds;
- Server health smoke test;
- WebAdmin import/health smoke test;
- VPN gateway image smoke test;
- WebAdmin VPN profile lifecycle smoke test;
- Save Configuration / Restart Server regression coverage through the test suite.

## 2. Dependencies — `.github/workflows/dependencies.yml`

Purpose: validate dependency and image changes separately from normal feature validation.

Checks:

- `uv.lock`;
- core and WebAdmin dependency graphs;
- `pip check` / `uv pip check`;
- advisory dependency audit;
- dependency-sensitive regression tests;
- Server/WebAdmin/VPN image builds.

It also runs weekly. Workflow-only and documentation-only changes do not trigger dependency validation.

## 3. Version bump — `.github/workflows/version-bump.yml`

Purpose: prepare a coordinated 2.x release.

Manual input:

```text
2.1.0
```

The workflow:

1. verifies semantic versioning and requires the new version to be greater than the current one;
2. creates `release/<version>`;
3. updates:
   - `SERVER_VERSION`;
   - `FORK_VERSION`;
   - `webadmin/WEBADMIN_VERSION`;
   - `pyproject.toml`;
   - `uv.lock`;
   - current-version references in `README.md` and `QUICKSTART.md`;
4. creates `docs/releases/v<version>.md`;
5. runs repository/lock validation;
6. pushes the release branch;
7. opens a pull request to `main`.

Merge the PR only after **CI** and **Dependencies** are green.

## 4. Release — `.github/workflows/release.yml`

Purpose: publish a validated 2.x version.

It can run from:

- an existing `v2.x.y` tag; or
- manual input of a version already present on `main`.

The workflow:

1. validates the coordinated version contract;
2. creates or verifies the release tag safely;
3. validates dependencies;
4. runs deterministic and network integration tests;
5. validates Compose variants;
6. builds Server, WebAdmin and VPN images;
7. smoke-tests all three packages;
8. publishes version, major and latest tags to GHCR;
9. mirrors the validated images to Docker Hub when credentials are configured;
10. verifies anonymous package pulls;
11. creates or updates the GitHub Release.

Published release tags are treated as immutable.

## 5. Upstream review — `.github/workflows/upstream-review.yml`

Purpose: monitor the principal repository without turning the fork into a mirror.

Principal:

```text
andrewhack/stremio-libtorrent-server
```

The workflow:

- fetches principal `main`;
- compares it with `.github/UPSTREAM_BASE`;
- classifies changed files as:
  - `ALREADY_INTEGRATED`;
  - `SAFE_CANDIDATE`;
  - `MANUAL_RECONCILE`;
  - `PROTECTED`;
- uploads an assessment artifact;
- writes the assessment to the job summary;
- opens or updates an issue when review is required.

It does **not**:

- merge upstream;
- pull upstream into `main`;
- create automatic sync branches;
- update `.github/UPSTREAM_BASE`;
- modify fork-owned runtime paths.

Accepted upstream changes must be implemented deliberately on a feature or `upstream-import/*` branch, validated by CI, and only then integrated.

## Permanent branches

The intended long-lived branch set is:

```text
main
develop/2.x
legacy/1.x
```

Temporary branches use:

```text
feature/*
fix/*
hotfix/*
release/*
upstream-import/*
```

Temporary branches should be deleted after integration.

## Release flow

```text
develop / feature / fix
        ↓
       CI
        ↓
Version bump workflow
        ↓
release/X.Y.Z
        ↓
CI + Dependencies
        ↓
merge to main
        ↓
Release workflow
        ↓
tag + GHCR + Docker Hub + GitHub Release
```

## Safety rules

- Never run `git merge upstream/main` as the normal update process.
- Never delete persistent Docker volumes during application upgrade.
- Never move a tag after a GitHub Release has been published.
- Never bypass the coordinated Server/Fork/WebAdmin/core version contract for 2.x.
- Keep base `compose.yaml` hardware-agnostic; VAAPI and NVIDIA are overlays.
