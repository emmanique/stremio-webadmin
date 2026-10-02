# v2.0.6

## Gluetun namespace lifecycle hardening

This release fixes a lifecycle edge case in the unified Compose stack when the
Gluetun container is recreated during an image upgrade.

Stremio uses `network_mode: service:gluetun`. Docker resolves that relationship
to the gateway container ID when Stremio is created. If Gluetun is later
recreated while Stremio is left untouched, Stremio can remain attached to the
old container namespace.

The normal `start.sh` upgrade path now performs a post-start integrity check:

- If Stremio already references the current Gluetun container ID, no action is taken.
- If the namespace is stale, only `stremio-libtorrent-server` is recreated.
- The repair uses the existing Compose configuration and GPU overlay detection.
- The script verifies the repaired namespace and fails closed if it still does not match.
- Pi-hole and WebAdmin are not unnecessarily recreated by the repair step.

Regression tests cover both the stale-namespace repair path and the no-op path
for an already-correct namespace.

## Upgrade safety

Persistent Docker volumes and WebAdmin configuration are unchanged. The release
does not require changes to the base hardware-agnostic Compose definition.
