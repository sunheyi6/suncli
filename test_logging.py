"""Test script to verify logging functionality."""

import os
import asyncio

# Set debug log level
os.environ["SUN_LOG_LEVEL"] = "DEBUG"

from sun_cli.chat import ChatSession
from rich.console import Console

async def test_logging():
    """Test logging functionality."""
    console = Console()
    session = ChatSession(console)
    
    # Test a query that should trigger web search
    await session.stream_message("Python最新版本是什么？")
    
    await session.client.aclose()

if __name__ == "__main__":
    asyncio.run(test_logging())
