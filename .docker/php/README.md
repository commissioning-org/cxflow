# PHP (Docker) image

This folder defines the PHP + Apache image used by the `app`, `worker`, and `scheduler` services.

## What’s included

### Dockerfile

- Base image: `php:8.3-apache`
- Common Laravel PHP extensions:
  - `pdo_mysql`, `mbstring`, `bcmath`, `pcntl`, `exif`, `sockets`, `zip`, `intl`, `gd`, `opcache`
  - `redis` via PECL
- Optional features via build args:
  - `INSTALL_SQLSRV` (default: `true`) — installs Microsoft ODBC + `sqlsrv` / `pdo_sqlsrv`
  - `INSTALL_XDEBUG` (default: `false`) — installs Xdebug for local debugging

### Runtime entrypoint (`docker-entrypoint.sh`)

On container start it can:

- Create Laravel writable dirs (`storage`, `bootstrap/cache`)
- Optionally remap `www-data` UID/GID to match your host (helps with bind-mount permissions)
- Generate PHP ini overrides from environment variables (no rebuild required)
- If Xdebug is installed, generate Xdebug configuration from env variables

## Environment variables (runtime)

These are read at container startup:

- Permissions:
  - `FIX_PERMISSIONS=1` — chown `storage` and `bootstrap/cache` to `www-data`
  - `PUID`, `PGID` — remap `www-data` uid/gid (e.g. your host uid/gid)

- PHP ini overrides:
  - `PHP_MEMORY_LIMIT` (e.g. `512M`)
  - `PHP_UPLOAD_MAX_FILESIZE` (e.g. `64M`)
  - `PHP_POST_MAX_SIZE` (e.g. `64M`)
  - `PHP_MAX_EXECUTION_TIME` (e.g. `120`)
  - `PHP_MAX_INPUT_VARS` (e.g. `3000`)

- Xdebug (only if built with `INSTALL_XDEBUG=true`):
  - `XDEBUG_MODE` (e.g. `off`, `develop`, `debug`, `coverage`)
  - `XDEBUG_START_WITH_REQUEST` (e.g. `trigger`, `yes`)
  - `XDEBUG_CLIENT_HOST` (default: `host.docker.internal`)
  - `XDEBUG_CLIENT_PORT` (default: `9003`)
  - `XDEBUG_LOG_LEVEL` (default: `0`)
  - `XDEBUG_DISCOVER_CLIENT_HOST` (default: `0`)

## Notes

- The image defines a Docker healthcheck that calls `http://localhost/healthz`.
- For production, you typically set `display_errors=0` and tune headers/caching differently.
