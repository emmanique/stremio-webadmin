# Branching model — 2.x

The 2.x line uses a controlled promotion model designed to keep development, stabilization and production releases separate.

## Branches

```text
main
  └─ production only; every 2.x commit must correspond to a validated release

develop/2.x
  └─ integration branch for the next 2.x release
       ├─ feature/<name>
       ├─ fix/<name>
       └─ dependency update PRs

release/2.x.y
  └─ release stabilization; bug fixes, documentation and version/release metadata only

hotfix/2.x.y
  └─ urgent production correction branched from main
```

## Promotion

```text
feature/*
    ↓ PR + 2.x Continuous Validation
develop/2.x
    ↓ release cut
release/2.x.y
    ↓ complete validation + release candidate tests
main
    ↓ annotated tag v2.x.y
2.x Release workflow
    ↓
GHCR + Docker Hub + GitHub Release
```

## Rules

- `main` is never used for feature development.
- `develop/2.x` must stay deployable and pass the full 2.x CI gate.
- Feature branches are deleted after merge.
- `release/2.x.y` accepts only release stabilization changes.
- A release tag must exactly match the unified version in `SERVER_VERSION`, `FORK_VERSION`, `webadmin/WEBADMIN_VERSION` and `pyproject.toml`.
- Hotfixes start from `main`, are released through the same validation gate, and are merged back into `develop/2.x`.
- Dependabot targets `develop/2.x`; dependency PRs do not publish packages.
- The legacy 1.x publication workflow is restricted to 1.x tags.

## Suggested branch protections

### main

Require:
- pull request before merge;
- successful `2.x Continuous Validation / Functional and packaging validation`;
- no force pushes;
- no branch deletion;
- linear history;
- at least one approval when collaborators are present.

### develop/2.x

Require:
- successful 2.x CI;
- no force pushes;
- resolved review conversations.

### release/2.x.y

Require:
- successful 2.x CI;
- no force pushes after release candidate testing starts.

## Release procedure

1. Ensure `develop/2.x` is green.
2. Create `release/2.x.y`.
3. Set all unified version files to `2.x.y`.
4. Add `docs/releases/v2.x.y.md`.
5. Run the complete CI and deployment smoke tests.
6. Merge the release branch into `main`.
7. Create annotated tag `v2.x.y` on the validated main commit.
8. The `2.x Release` workflow builds, tests and publishes Server, WebAdmin and VPN images.
9. Merge any release-only fixes back into `develop/2.x`.

## Legacy

The 1.x line is retained only for historical maintenance. New features belong to 2.x.
