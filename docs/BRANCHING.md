# Branching and release model

The repository uses a small, long-lived branch model. Do not create a new permanent branch for every application version.

## Long-lived branches

| Branch | Purpose | Direct pushes |
|---|---|---|
| `main` | Production. Every commit must be releasable. Release tags are created from here. | Protected; PR only |
| `development` | Integration branch for the next release. | Protected; PR only |

## Temporary branches

| Pattern | Created from | Merged into | Lifetime |
|---|---|---|---|
| `feature/<short-name>` | `development` | `development` | Delete after merge |
| `fix/<short-name>` | `development` | `development` | Delete after merge |
| `release/<x.y.z>` | `development` | `main`, then sync `main` back to `development` | Only while stabilising a release |
| `hotfix/<short-name>` | `main` | `main`, then sync `main` back to `development` | Only for urgent production fixes |

Do not create version branches such as `development/2.x`, `maintenance/2.0.x`, or a new long-lived branch for each incremental release.

## Normal development

1. Update local `development`.
2. Create `feature/<name>` or `fix/<name>`.
3. Implement code, tests and documentation in the same PR.
4. Open a PR to `development`.
5. Fast CI must pass before merge.
6. Delete the temporary branch after merge.

## Release

1. When `development` is ready, run **Prepare release** with the target semantic version.
2. The workflow creates one temporary `release/<x.y.z>` branch and a PR to `main`.
3. Only release stabilisation changes are allowed on that branch.
4. The PR to `main` runs the complete regression suite, image smoke tests, deployment-package validation and documentation contract.
5. Merge the PR.
6. Run/tag the Release workflow from `main`.
7. Delete `release/<x.y.z>` after publication.
8. Merge/sync `main` back into `development` so both long-lived branches contain the released state.

## Hotfix

1. Create `hotfix/<name>` from `main`.
2. Add the fix, regression test and documentation/upgrade impact when applicable.
3. PR to `main`; complete regression is mandatory.
4. Release a patch version.
5. Sync `main` back to `development` and delete the hotfix branch.

## Versioning responsibilities

`FORK_VERSION` and `webadmin/WEBADMIN_VERSION` track the platform release. `SERVER_VERSION` and `pyproject.toml` track the integrated upstream/core release independently.

## Recommended branch protection

For `main`, require pull requests, **Fast CI** and **Full regression**. Do not allow routine direct pushes. For `development`, require pull requests and **Fast CI**. Release tags should be treated as immutable after publication.

## Legacy branch cleanup

Historical version branches may remain temporarily for traceability, but they are not workflow targets and must not be used for new work. In particular, `develop/2.x` is legacy; `development` is the single integration branch. Old feature/fix/release/hotfix branches should be deleted after their merge/tag when no longer required for audit or rollback.
