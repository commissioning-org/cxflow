#!/usr/bin/env python3
"""
CXFlow main entry point.

This script provides a unified interface to all CXFlow capabilities.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cxflow_core.cli import main

if __name__ == "__main__":
    main()
