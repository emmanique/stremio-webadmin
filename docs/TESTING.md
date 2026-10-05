# Test strategy

Testing is split by purpose so normal development remains fast while production releases remain conservative.

## 1. Fast CI (`ci-fast.yml`)

Runs on PRs to `development`/`main` and pushes to those branches.

It validates:

- repository contract and version-file consistency;
- Python/shell/PowerShell/JavaScript syntax;
- Ruff lint;
- Docker Compose configuration and hardware-neutral base topology;
- deterministic non-integration pytest suite;
- documentation/change contract on pull requests.

This is the minimum merge gate for normal feature and fix work.

## 2. Dependency validation (`dependencies.yml`)

Runs only when dependency manifests/images change, weekly, or manually. It checks lock consistency and dependency health independently of functional CI.

## 3. Full regression (`regression.yml`)

Runs for PRs targeting `main`, manually, and as a reusable gate for publishing a release or validating upstream integration.

It executes:

- all Fast CI checks;
- complete deterministic regression tests;
- network/integration tests with retry;
- build of Server, WebAdmin and VPN images;
- runtime smoke tests for all images;
- release deployment-package generation and content validation;
- clean-install simulation by extracting the deployment package, creating a fresh `.env` from `.env.example` and resolving the stack through `start.sh config`.

A release must never bypass this workflow.

## 4. Release (`release.yml`)

Publishing is not itself a substitute for testing. Release first calls the reusable Full regression workflow. Only after it succeeds are images and release artefacts published.

## Regression test rule

Every bug fix should add or update a test that fails before the fix and passes after it. Every new user-visible capability should have at least one automated behavioural test where technically practical.

Tests that need live networking/libtorrent are marked `integration`; deterministic tests must not depend on public network availability.


## Functional regression ownership

Every user-visible capability and every regression fix must have an automated test and must be assigned to at least one functional group in `tools/ci/functional-regression.matrix`.

Current functional contracts are:

- `core-torrent`: torrent lifecycle, cache, pins, trackers, DHT, peer/seed policy and statistics.
- `playback-streaming`: streaming, HLS, playback sessions, prefetch, proxy, resume and Web Player integration.
- `transcoding`: FFmpeg policy, converter command generation, hardware/HDR policy and transcoding lifecycle.
- `subtitles`: embedded/external subtitles, ASS/SRT/VTT routes and HLS subtitle integration.
- `library`: My Library, authentication, addon, metadata, download, resume and Continue Watching.
- `vpn-network`: VPN, DNS/network guard, certificates, nginx and compose VPN topology.
- `webadmin-config`: WebAdmin API/UI, settings lifecycle, health, metrics and runtime status.
- `version-update`: component versions, update lifecycle and configuration preservation.
- `packaging-install`: first-install/runtime packaging contracts.

### Mandatory development sequence

1. Add or change the feature.
2. Add a regression test that protects its expected behaviour.
3. Assign the test to its functional group in the matrix.
4. Run the feature group locally, for example:
   `bash tools/ci/functional-regression.sh library`
5. Run the accumulated regression locally:
   `bash tools/ci/functional-regression.sh all`
6. Push only after the local accumulated regression passes.
7. GitHub Actions runs the same versioned matrix. A manually selected group is always followed by the complete accumulated matrix.
8. Before upstream integration, release or production promotion, `tools/ci/full-regression.sh` runs the functional matrix plus deterministic, integration, image-build, runtime-smoke and clean-install gates.

A new `tests/test_*.py` file that is not classified in the matrix causes CI to fail. Removing a functional test therefore requires an explicit matrix change that is visible in code review.

Local DEV and GitHub DEV use the same scripts from the repository; the test definition must not live only on the .245 server.
