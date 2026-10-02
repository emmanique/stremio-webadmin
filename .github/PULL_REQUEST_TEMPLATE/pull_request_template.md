## Change

Describe what changed and why.

## Validation

- [ ] I added/updated automated tests for changed behaviour where practical.
- [ ] Fast CI passes locally or in GitHub Actions.
- [ ] I did not commit `.env`, credentials, local IP addresses, generated caches or backup files.

## Documentation / operations

- [ ] `README.md` was updated if this changes a user-visible feature, configuration variable, installation step, port, volume, runtime topology, or upgrade procedure.
- [ ] `.env.example` was updated if configuration variables changed.
- [ ] Upgrade/migration instructions were documented if an existing installation needs manual action.
- [ ] Release notes describe the user-visible impact for release-bound changes.

## Compatibility

- [ ] Existing persistent volumes remain compatible, or migration steps are explicitly documented.
- [ ] Base `compose.yaml` remains hardware-neutral; GPU-specific requirements stay in overlays.
