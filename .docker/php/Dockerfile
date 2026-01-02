FROM php:8.3-apache

ARG INSTALL_SQLSRV=true
ARG INSTALL_XDEBUG=false

# Default docroot (docker-compose may override via environment)
ENV APACHE_DOCUMENT_ROOT=/var/www/html/public

# Composer convenience (dev containers often run as root)
ENV COMPOSER_ALLOW_SUPERUSER=1

# System deps for common Laravel needs
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    git \
    unzip \
    zip \
    libzip-dev \
    libicu-dev \
    libonig-dev \
    libpng-dev \
    libjpeg62-turbo-dev \
    libfreetype6-dev \
    ca-certificates \
    curl \
    gnupg \
    apt-transport-https \
  && rm -rf /var/lib/apt/lists/*

# PHP extensions
RUN docker-php-ext-configure gd --with-freetype --with-jpeg \
  && docker-php-ext-install -j$(nproc) \
    pdo_mysql \
    mbstring \
    bcmath \
    pcntl \
    exif \
    sockets \
    zip \
    intl \
    gd \
    opcache

# Redis extension (recommended for Laravel cache/queue)
RUN pecl install redis \
  && docker-php-ext-enable redis

# Optional SQL Server support (msodbcsql + sqlsrv/pdo_sqlsrv)
# Default: enabled to preserve current behavior.
ENV ACCEPT_EULA=Y
RUN set -eux; \
  if [ "${INSTALL_SQLSRV}" = "true" ]; then \
    apt-get update; \
    apt-get install -y --no-install-recommends $PHPIZE_DEPS unixodbc unixodbc-dev; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft-prod.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
      > /etc/apt/sources.list.d/microsoft-prod.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends msodbcsql18; \
    pecl install sqlsrv pdo_sqlsrv; \
    docker-php-ext-enable sqlsrv pdo_sqlsrv; \
    rm -rf /tmp/pear; \
    apt-get purge -y --auto-remove $PHPIZE_DEPS; \
    rm -rf /var/lib/apt/lists/*; \
  fi

# Optional Xdebug (dev only)
RUN set -eux; \
  if [ "${INSTALL_XDEBUG}" = "true" ]; then \
    apt-get update; \
    apt-get install -y --no-install-recommends $PHPIZE_DEPS; \
    pecl install xdebug; \
    docker-php-ext-enable xdebug; \
    rm -rf /tmp/pear; \
    apt-get purge -y --auto-remove $PHPIZE_DEPS; \
    rm -rf /var/lib/apt/lists/*; \
  fi

# Apache modules for Laravel + useful defaults
RUN set -eux; \
  a2enmod rewrite headers env expires deflate status remoteip reqtimeout; \
  a2enmod proxy proxy_http; \
  a2enmod brotli || true

# Apache vhost + shared config snippets
COPY .docker/apache/000-default.conf /etc/apache2/sites-available/000-default.conf
COPY .docker/apache/conf-available/ /etc/apache2/conf-available/

RUN set -eux; \
  a2enconf 00-base 10-headers 20-compression 30-caching 40-remoteip 50-status 60-healthz 70-ml-proxy; \
  mkdir -p /var/www/_health; \
  printf 'ok\n' > /var/www/_health/healthz.txt

# PHP tuning for Laravel
COPY .docker/php/conf.d/laravel.ini /usr/local/etc/php/conf.d/99-laravel.ini
COPY .docker/php/conf.d/00-base.ini /usr/local/etc/php/conf.d/00-base.ini
COPY .docker/php/conf.d/20-performance.ini /usr/local/etc/php/conf.d/20-performance.ini

# Entrypoint: env-driven ini overrides + optional permission fixes
COPY .docker/php/docker-entrypoint.sh /usr/local/bin/docker-entrypoint
RUN chmod +x /usr/local/bin/docker-entrypoint

# Install Composer (copy from official image)
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

# Keep permissions sane for mounted volumes
RUN chown -R www-data:www-data /var/www \
  && chmod -R 755 /var/www

HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD curl -fsS http://localhost/healthz || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
CMD ["apache2-foreground"]
