#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[entrypoint] $*" >&2
}

write_ini_kv() {
  local file="$1" key="$2" value="$3"
  # Skip empty values
  [[ -z "$value" ]] && return 0
  printf '%s=%s\n' "$key" "$value" >> "$file"
}

# Optionally remap www-data to match host UID/GID (helps with bind mounts).
# Usage:
#   PUID=$(id -u) PGID=$(id -g) docker compose up
if [[ -n "${PUID:-}" && -n "${PGID:-}" ]]; then
  if getent group www-data >/dev/null 2>&1; then
    groupmod -o -g "$PGID" www-data >/dev/null 2>&1 || true
  fi
  if id www-data >/dev/null 2>&1; then
    usermod -o -u "$PUID" www-data >/dev/null 2>&1 || true
  fi
fi

# Ensure Laravel writable directories exist when the code is bind-mounted.
# This is intentionally light-touch; set FIX_PERMISSIONS=1 if you want chown.
for rel in storage bootstrap/cache; do
  path="/var/www/html/$rel"
  if [[ -e "/var/www/html" ]]; then
    mkdir -p "$path" || true
    if [[ "${FIX_PERMISSIONS:-0}" = "1" ]]; then
      chown -R www-data:www-data "$path" || true
    fi
  fi
done

# Generate runtime PHP ini overrides from environment variables.
# This avoids rebuilding the image for common tweaks.
ENV_INI="/usr/local/etc/php/conf.d/zz-runtime-env.ini"
: > "$ENV_INI"

write_ini_kv "$ENV_INI" "memory_limit" "${PHP_MEMORY_LIMIT:-}"
write_ini_kv "$ENV_INI" "upload_max_filesize" "${PHP_UPLOAD_MAX_FILESIZE:-}"
write_ini_kv "$ENV_INI" "post_max_size" "${PHP_POST_MAX_SIZE:-}"
write_ini_kv "$ENV_INI" "max_execution_time" "${PHP_MAX_EXECUTION_TIME:-}"
write_ini_kv "$ENV_INI" "max_input_vars" "${PHP_MAX_INPUT_VARS:-}"

# Xdebug is optional. If it’s installed and XDEBUG_MODE is set, write a config.
if php -m 2>/dev/null | grep -qi '^xdebug$'; then
  XDEBUG_INI="/usr/local/etc/php/conf.d/zz-xdebug.ini"
  : > "$XDEBUG_INI"

  # Common options: off, develop, debug, coverage
  write_ini_kv "$XDEBUG_INI" "xdebug.mode" "${XDEBUG_MODE:-off}"
  write_ini_kv "$XDEBUG_INI" "xdebug.start_with_request" "${XDEBUG_START_WITH_REQUEST:-trigger}"
  write_ini_kv "$XDEBUG_INI" "xdebug.client_host" "${XDEBUG_CLIENT_HOST:-host.docker.internal}"
  write_ini_kv "$XDEBUG_INI" "xdebug.client_port" "${XDEBUG_CLIENT_PORT:-9003}"
  write_ini_kv "$XDEBUG_INI" "xdebug.log_level" "${XDEBUG_LOG_LEVEL:-0}"

  # Helpful when debugging CLI scripts (artisan, queue worker)
  write_ini_kv "$XDEBUG_INI" "xdebug.discover_client_host" "${XDEBUG_DISCOVER_CLIENT_HOST:-0}"
fi

# Composer quality-of-life: prevent warnings when running as root in dev
export COMPOSER_ALLOW_SUPERUSER="${COMPOSER_ALLOW_SUPERUSER:-1}"

exec "$@"
