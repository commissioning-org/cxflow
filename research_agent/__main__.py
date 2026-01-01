"""Entry point for running research_agent as a module.

This module provides:
- Proper error handling and exit codes
- Logging configuration
- Environment variable support
- Signal handling for graceful shutdown
- Exception formatting for user-friendly errors

Usage:
    python -m research_agent <command> [options]
    
Examples:
    python -m research_agent report owner/repo
    python -m research_agent search owner/repo "query"
    python -m research_agent security owner/repo
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import traceback
from typing import NoReturn, Optional

from .cli import main, Colors


# ============================================================================
# Exit Codes
# ============================================================================

class ExitCode:
    """Standard exit codes."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    USAGE_ERROR = 2
    PERMISSION_ERROR = 3
    NOT_FOUND = 4
    NETWORK_ERROR = 5
    INTERRUPTED = 130  # 128 + SIGINT


# ============================================================================
# Logging Configuration
# ============================================================================

def _configure_logging() -> None:
    """Configure logging based on environment variables."""
    level_str = os.environ.get("RESEARCH_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_str, logging.WARNING)
    
    log_format = os.environ.get(
        "RESEARCH_LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    log_file = os.environ.get("RESEARCH_LOG_FILE")
    
    handlers = []
    
    # File handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        except (OSError, IOError):
            pass
    
    # Console handler for debug mode
    if level <= logging.DEBUG:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers if handlers else None,
    )
    
    # Reduce noise from other libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("git").setLevel(logging.WARNING)


# ============================================================================
# Signal Handling
# ============================================================================

_interrupted = False


def _signal_handler(signum: int, frame) -> None:
    """Handle interrupt signals gracefully."""
    global _interrupted
    
    if _interrupted:
        # Second interrupt - force exit
        sys.stderr.write("\nForce quit.\n")
        sys.exit(ExitCode.INTERRUPTED)
    
    _interrupted = True
    sys.stderr.write(f"\n{Colors.YELLOW}⚠ Interrupted. Press Ctrl+C again to force quit.{Colors.RESET}\n")


def _setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)


# ============================================================================
# Error Formatting
# ============================================================================

def _format_exception(exc: Exception, verbose: bool = False) -> str:
    """Format an exception for display."""
    exc_type = type(exc).__name__
    message = str(exc)
    
    # Known exception types with friendly messages
    friendly_messages = {
        "FileNotFoundError": "File or directory not found",
        "PermissionError": "Permission denied",
        "ConnectionError": "Network connection failed",
        "TimeoutError": "Operation timed out",
        "subprocess.CalledProcessError": "Command execution failed",
        "json.JSONDecodeError": "Invalid JSON format",
    }
    
    friendly = friendly_messages.get(exc_type, exc_type)
    
    if verbose:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return f"{Colors.RED}Error:{Colors.RESET} {friendly}\n{message}\n\n{Colors.DIM}Traceback:\n{tb}{Colors.RESET}"
    
    return f"{Colors.RED}Error:{Colors.RESET} {friendly}: {message}"


def _get_exit_code(exc: Exception) -> int:
    """Determine exit code based on exception type."""
    exc_type = type(exc).__name__
    
    if exc_type in ("FileNotFoundError", "NotADirectoryError"):
        return ExitCode.NOT_FOUND
    if exc_type in ("PermissionError",):
        return ExitCode.PERMISSION_ERROR
    if exc_type in ("ConnectionError", "TimeoutError", "urllib3.exceptions.MaxRetryError"):
        return ExitCode.NETWORK_ERROR
    if exc_type in ("ValueError", "TypeError", "argparse.ArgumentError"):
        return ExitCode.USAGE_ERROR
    
    return ExitCode.GENERAL_ERROR


# ============================================================================
# Environment Configuration
# ============================================================================

def _check_environment() -> None:
    """Check and configure environment."""
    # Disable color if requested
    if os.environ.get("NO_COLOR") or os.environ.get("RESEARCH_NO_COLOR"):
        Colors.disable()
    
    # Set default clone root from environment
    if "RESEARCH_CLONE_ROOT" not in os.environ:
        os.environ.setdefault("RESEARCH_CLONE_ROOT", ".repos")
    
    # Enable debug mode
    if os.environ.get("RESEARCH_DEBUG"):
        os.environ.setdefault("RESEARCH_LOG_LEVEL", "DEBUG")


# ============================================================================
# Main Entry Point
# ============================================================================

def run() -> int:
    """Run the CLI with proper setup and error handling.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Setup
    _check_environment()
    _configure_logging()
    _setup_signal_handlers()
    
    logger = logging.getLogger("research_agent")
    logger.debug("Starting research agent")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Arguments: {sys.argv}")
    
    try:
        # Run the main CLI
        exit_code = main()
        logger.debug(f"Completed with exit code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.debug("Interrupted by user")
        sys.stderr.write(f"\n{Colors.YELLOW}⚠ Operation cancelled.{Colors.RESET}\n")
        return ExitCode.INTERRUPTED
        
    except SystemExit as e:
        # Pass through SystemExit
        return e.code if isinstance(e.code, int) else ExitCode.GENERAL_ERROR
        
    except Exception as e:
        # Handle unexpected errors
        logger.exception("Unexpected error")
        verbose = os.environ.get("RESEARCH_DEBUG") or "--verbose" in sys.argv or "-v" in sys.argv
        sys.stderr.write(_format_exception(e, verbose=verbose) + "\n")
        return _get_exit_code(e)


def entry_point() -> NoReturn:
    """Entry point that calls sys.exit with the result.
    
    This is the function referenced in pyproject.toml or setup.py
    for the console script entry point.
    """
    sys.exit(run())


# Allow running with: python -m research_agent
if __name__ == "__main__":
    entry_point()
