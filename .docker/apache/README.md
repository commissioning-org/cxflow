# Apache (Docker) configuration

This folder contains the Apache configuration used by the `php:8.3-apache` image in `.docker/php/Dockerfile`.

## What’s included

- `000-default.conf`
  - The default vhost for the container.
  - Uses `${APACHE_DOCUMENT_ROOT}` for `DocumentRoot` (default set in the Dockerfile to `/var/www/html/public`).
  - Uses the custom access log format `vhost_combined` defined in `conf-available/00-base.conf`.

- `conf-available/00-base.conf`
  - Safe baseline hardening (`ServerTokens Prod`, `TraceEnable Off`, etc.)
  - Keepalive and timeout tuning
  - Custom `LogFormat` (`vhost_combined`)

- `conf-available/10-headers.conf`
  - Common security headers suitable for dev and most production environments.
  - Intentionally does **not** enable HSTS by default (TLS is usually terminated elsewhere).

- `conf-available/20-compression.conf`
  - gzip via `mod_deflate`
  - brotli via `mod_brotli` (enabled if available)

- `conf-available/30-caching.conf`
  - Strong caching for Vite build outputs under `/build/` (typically fingerprinted)
  - Mild caching for other static assets

- `conf-available/40-remoteip.conf`
  - Uses `X-Forwarded-For` when behind a proxy so access logs show the real client IP.

- `conf-available/50-status.conf`
  - Enables `/server-status` restricted to localhost/private networks.

- `conf-available/60-healthz.conf`
  - Adds a simple `/healthz` endpoint served from `/var/www/_health/healthz.txt` so basic container health doesn’t depend on Laravel routing.

## Notes

- Modules are enabled in `.docker/php/Dockerfile` (`a2enmod ...`).
- Config snippets are enabled via `a2enconf`.
- If you add new `.conf` files under `conf-available/`, remember to enable them in the Dockerfile.
