# Container publication model

Production container images are published only from the public production repository:
https://github.com/emmanique/stremio-webadmin

The authoritative production registry is GHCR:

```text
ghcr.io/emmanique/stremio-server:<VERSION>
ghcr.io/emmanique/stremio-webadmin:<VERSION>
ghcr.io/emmanique/stremio-vpn:<VERSION>
```

Stable releases may additionally publish `latest`, but only after the production release gate succeeds.

Development images are built only from:
https://github.com/emmanique/stremio-webadmin-dev

They use isolated package names and never publish production `latest`:

```text
ghcr.io/emmanique/stremio-server-dev:<DEV_VERSION>
ghcr.io/emmanique/stremio-webadmin-dev:<DEV_VERSION>
ghcr.io/emmanique/stremio-vpn-dev:<DEV_VERSION>
```

The historical repository and its image names are not publication targets.

## Release authority

```text
andrewhack/stremio-libtorrent-server
        -> controlled Core integration
emmanique/stremio-webadmin-dev
        -> development CI / regression / DEV images
emmanique/stremio-webadmin
        -> validated production tags / releases / stable images
```

A production image must be traceable to an immutable public Git tag and GitHub Release. DEV images must be traceable to a commit in the DEV repository.

Credentials are supplied only through repository secrets or an authenticated local registry session and must never be committed.
