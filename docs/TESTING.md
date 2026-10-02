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
