# Docker Hub publication

The project publishes the same validated release artifacts to two registries:

```text
Primary registry:  GitHub Container Registry (GHCR)
Mirror registry:   Docker Hub
```

The normal runtime/update path continues to use GHCR. Docker Hub is maintained as a public mirror for users and environments that prefer Docker Hub.

## Docker Hub repository

```text
edmanique/stremio-libtorrent-server-webadmin
```

## Current tag model

Server:

```text
edmanique/stremio-libtorrent-server-webadmin:latest
edmanique/stremio-libtorrent-server-webadmin:<SERVER_VERSION>
```

WebAdmin:

```text
edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
edmanique/stremio-libtorrent-server-webadmin:webadmin-<WEBADMIN_VERSION>
```

VPN/Gluetun gateway:

```text
edmanique/stremio-libtorrent-server-webadmin:vpn-latest
edmanique/stremio-libtorrent-server-webadmin:vpn-<SERVER_VERSION>
```

For the current release:

```text
edmanique/stremio-libtorrent-server-webadmin:latest
edmanique/stremio-libtorrent-server-webadmin:1.6.9-server.18

edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
edmanique/stremio-libtorrent-server-webadmin:webadmin-1.4.1

edmanique/stremio-libtorrent-server-webadmin:vpn-latest
edmanique/stremio-libtorrent-server-webadmin:vpn-1.6.9-server.18
```

## Pull examples

```bash
docker pull edmanique/stremio-libtorrent-server-webadmin:latest
docker pull edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
docker pull edmanique/stremio-libtorrent-server-webadmin:vpn-latest
```

For reproducible deployments, prefer versioned tags:

```bash
docker pull edmanique/stremio-libtorrent-server-webadmin:1.6.9-server.18
docker pull edmanique/stremio-libtorrent-server-webadmin:webadmin-1.4.1
docker pull edmanique/stremio-libtorrent-server-webadmin:vpn-1.6.9-server.18
```

## GitHub Actions secrets

Docker Hub publication uses repository secrets and never stores credentials in tracked files.

Required secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

The token must be a Docker Hub Personal Access Token with permission to push images to:

```text
edmanique/stremio-libtorrent-server-webadmin
```

Do not commit the token to `.env`, workflow files, scripts, documentation, screenshots or release notes.

## Automated publication

`.github/workflows/release-package.yml` performs the normal release publication.

The flow is:

```text
validated release tag
        |
        v
build Server / WebAdmin / VPN
        |
        v
smoke tests
        |
        v
publish GHCR versioned + latest tags
        |
        v
retag the same validated images
        |
        v
publish Docker Hub versioned + latest tags
```

Docker Hub images are therefore not independently rebuilt from source after the GHCR release. Both registries receive the same validated image artifacts.

`.github/workflows/dockerhub-sync.yml` can be run independently to synchronize the current stable GHCR images to Docker Hub without rebuilding them.

## Manual publication helper

For a controlled manual publication, the repository includes:

```text
docker/publish.sh
docker/push-readme.sh
```

Default Docker Hub target:

```text
edmanique/stremio-libtorrent-server-webadmin
```

Authenticate first:

```bash
docker login -u edmanique
```

Use a Docker Hub Personal Access Token as the password.

Then run the publisher according to the intended release procedure. `docker/publish.sh` includes local build/version checks and smoke validation before pushing.

## Docker Hub Overview synchronization

Image publication and Docker Hub repository-description publication are separate operations.

`docker/push-readme.sh` attempts to synchronize `README.md` into the Docker Hub repository Overview through the Docker Hub API. Some Docker Hub token configurations permit registry push operations but do not grant the API scope required to update repository metadata. In that case image publication remains valid even if Overview synchronization returns HTTP `403 insufficient scope`.

The GitHub Actions workflow treats Overview synchronization as non-blocking so a metadata permission limitation does not invalidate an otherwise successful image release.

## Registry authority

GHCR remains authoritative for the application's default Compose/update mechanism:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn
```

Docker Hub provides the equivalent public mirror:

```text
edmanique/stremio-libtorrent-server-webadmin
```

If a versioned Docker Hub tag does not correspond to the same validated artifact published for that version in GHCR, publication must be treated as inconsistent and corrected before using `latest` as a stable reference.
