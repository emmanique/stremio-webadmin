# Repository workflows

The repository separates fast development feedback from production regression and publication.

## Fast CI — `.github/workflows/ci-fast.yml`

Runs for pushes and pull requests involving `main` or `development`, plus manual runs. It validates repository contracts, syntax/lint, Compose topology, deterministic tests and documentation/change rules.

## Dependencies — `.github/workflows/dependencies.yml`

Runs only when dependency manifests/images change, weekly, or manually. Dependency PRs target `development`.

## Full regression — `.github/workflows/regression.yml`

Runs for PRs targeting `main`, manually and as a reusable release/upstream gate. It executes deterministic and integration regression tests, builds Server/WebAdmin/VPN images, runs smoke tests and validates the generated deployment package.

## Prepare release — `.github/workflows/prepare-release.yml`

Creates a temporary `release/<version>` from `development`, updates version metadata, creates release-note placeholders and opens a PR to `main`. README/QUICKSTART changes are intentionally manual and must accurately describe the release.

## Release — `.github/workflows/release.yml`

After a release PR is merged to `main`, the workflow reads `FORK_VERSION`. If that version has no existing tag, it runs the full release gate and publishes images, an immutable version tag and deployment ZIP/TAR artefacts. Later `main` commits do not republish an already-tagged version. Manual and tag-triggered publication remain available.

## Upstream sync — `.github/workflows/upstream-sync.yml`

Upstream changes are isolated in the reusable `upstream/integration` branch, validated with Full regression and proposed to `development` through a PR. Upstream automation never promotes directly to `main`.
