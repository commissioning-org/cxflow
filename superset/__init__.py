"""
Apache Superset Integration Package.

Provides comprehensive integration with Apache Superset for:
- Dashboard and chart management
- Dataset and database connections
- User and role management
- Embedding and sharing
- Automated reporting
- SQL Lab operations

Version: 1.0.0
Compatible with: Apache Superset 3.0+
"""

__version__ = "1.0.0"
__author__ = "CxFlow Team"

from .client import SupersetClient, AsyncSupersetClient
from .config import SupersetConfig, DatabaseConfig, DatasetConfig
from .dashboards import DashboardManager, Dashboard, Chart
from .datasets import DatasetManager, Dataset, Column, Metric
from .databases import DatabaseManager, Database
from .security import SecurityManager, Role, Permission, User
from .embedding import EmbeddingManager, EmbeddedDashboard
from .reports import ReportManager, Report, ReportSchedule
from .sql_lab import SQLLabClient, Query, QueryResult

__all__ = [
    # Version
    "__version__",
    
    # Client
    "SupersetClient",
    "AsyncSupersetClient",
    
    # Config
    "SupersetConfig",
    "DatabaseConfig",
    "DatasetConfig",
    
    # Dashboards
    "DashboardManager",
    "Dashboard",
    "Chart",
    
    # Datasets
    "DatasetManager",
    "Dataset",
    "Column",
    "Metric",
    
    # Databases
    "DatabaseManager",
    "Database",
    
    # Security
    "SecurityManager",
    "Role",
    "Permission",
    "User",
    
    # Embedding
    "EmbeddingManager",
    "EmbeddedDashboard",
    
    # Reports
    "ReportManager",
    "Report",
    "ReportSchedule",
    
    # SQL Lab
    "SQLLabClient",
    "Query",
    "QueryResult",
]
