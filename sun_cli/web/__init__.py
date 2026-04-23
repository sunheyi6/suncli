"""Web server module for Sun CLI.

Provides FastAPI application for deploying Sun CLI as a web service.
"""

from .server import app

__all__ = ["app"]
