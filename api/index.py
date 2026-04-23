"""Vercel Serverless Function entry point for Sun CLI Web API.

This file is the bridge between Vercel's serverless platform
and the FastAPI application defined in sun_cli.web.server.

Usage:
    - Deploy to Vercel: `vercel --prod`
    - Local dev: `vercel dev` or `python -m uvicorn api.index:app --reload`
"""

import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sun_cli.web.server import app

# Export for Vercel ASGI handler
# Vercel will look for an ASGI-compatible `app` object
