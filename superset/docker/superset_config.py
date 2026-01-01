# -*- coding: utf-8 -*-
"""
Apache Superset Configuration

This configuration file is mounted into the Superset container
and provides customizations for the deployment.
"""

import os
from datetime import timedelta
from cachelib.redis import RedisCache

# =============================================================================
# SECRET KEY
# =============================================================================

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "changethissecretkey")

# =============================================================================
# DATABASE
# =============================================================================

SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{os.getenv('DATABASE_USER', 'superset')}:"
    f"{os.getenv('DATABASE_PASSWORD', 'superset')}@"
    f"{os.getenv('DATABASE_HOST', 'db')}:"
    f"{os.getenv('DATABASE_PORT', '5432')}/"
    f"{os.getenv('DATABASE_DB', 'superset')}"
)

# =============================================================================
# CACHE
# =============================================================================

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 1,
}

DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,  # 24 hours
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 2,
}

FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 3,
}

EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_explore_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 4,
}

# =============================================================================
# CELERY
# =============================================================================

class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    imports = (
        "superset.sql_lab",
        "superset.tasks.cache",
        "superset.tasks.scheduler",
    )
    task_annotations = {
        "sql_lab.get_sql_results": {
            "rate_limit": "100/s",
        },
    }
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": timedelta(minutes=1),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": timedelta(days=1),
        },
    }

CELERY_CONFIG = CeleryConfig

# =============================================================================
# FEATURE FLAGS
# =============================================================================

FEATURE_FLAGS = {
    # Dashboards
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_NATIVE_FILTERS_SET": True,
    "DASHBOARD_FILTERS_EXPERIMENTAL": True,
    
    # Embedding
    "EMBEDDED_SUPERSET": True,
    "EMBEDDABLE_CHARTS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    
    # SQL Lab
    "ENABLE_TEMPLATE_REMOVE_FILTERS": True,
    "ESTIMATE_QUERY_COST": True,
    "SCHEDULED_QUERIES": True,
    
    # Alerts & Reports
    "ALERT_REPORTS": True,
    
    # Charts
    "DASHBOARD_VIRTUALIZATION": True,
    "DRILL_TO_DETAIL": True,
    "HORIZONTAL_FILTER_BAR": True,
    
    # Security
    "ROW_LEVEL_SECURITY": True,
    "TAGGING_SYSTEM": True,
    
    # Other
    "ESCAPE_MARKDOWN_HTML": True,
    "GLOBAL_ASYNC_QUERIES": True,
}

# =============================================================================
# SECURITY
# =============================================================================

# Enable CORS for embedding
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["*"],  # Configure appropriately for production
}

# CSRF settings
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ["superset.views.api"]
WTF_CSRF_TIME_LIMIT = 60 * 60 * 24 * 365  # 1 year

# Guest token settings
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_SECRET = SECRET_KEY
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_TOKEN_JWT_EXP_SECONDS = 300  # 5 minutes

# =============================================================================
# SQL LAB
# =============================================================================

# Maximum rows returned by SQL Lab
SQL_MAX_ROW = 100000
DISPLAY_MAX_ROW = 10000

# Query timeout
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 300

# Async query settings
SQLLAB_ASYNC_TIME_LIMIT_SEC = 600
SQLLAB_DEFAULT_DBID = None
SQLLAB_CTAS_NO_LIMIT = True

# =============================================================================
# REPORTS
# =============================================================================

# Email configuration for reports
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "False").lower() == "true"
SMTP_SSL = os.getenv("SMTP_SSL", "False").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_MAIL_FROM = os.getenv("SMTP_MAIL_FROM", "superset@superset.local")

# Slack configuration for reports
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN", "")

# Screenshot settings for reports
WEBDRIVER_TYPE = "chrome"
WEBDRIVER_OPTION_ARGS = [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]

# =============================================================================
# MISC
# =============================================================================

# App name
APP_NAME = "Superset"

# Icons
APP_ICON = "/static/assets/images/superset-logo-horiz.png"
FAVICONS = [{"href": "/static/assets/images/favicon.png"}]

# Languages
LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
}

# Thumbnail caching
THUMBNAIL_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_thumb_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 5,
}

# Logging
LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
