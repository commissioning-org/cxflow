FROM php:8.3-apache

# System deps for common Laravel needs
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    git \
    unzip \
    zip \
    libzip-dev \
    libicu-dev \
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
    bcmath \
    pcntl \
    zip \
    intl \
    gd \
    opcache

# Redis extension (recommended for Laravel cache/queue)
RUN pecl install redis \
  && docker-php-ext-enable redis

# SQL Server support (msodbcsql + sqlsrv/pdo_sqlsrv)
# Mirrors the approach from: thiagoluna/laravel-apache-sqlsrv-docker
ENV ACCEPT_EULA=Y
RUN set -eux; \
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
  rm -rf /var/lib/apt/lists/*

# Apache modules for Laravel
RUN a2enmod rewrite headers env

# Set Apache to serve Laravel's /public
COPY .docker/apache/000-default.conf /etc/apache2/sites-available/000-default.conf

# PHP tuning for Laravel
COPY .docker/php/conf.d/laravel.ini /usr/local/etc/php/conf.d/99-laravel.ini

# Install Composer (copy from official image)
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

# Keep permissions sane for mounted volumes
RUN chown -R www-data:www-data /var/www \
  && chmod -R 755 /var/www
