"""MCP and Plugin system - external tool integration (s19)."""

from .client import MCPClient, MCPServer, ServerConfig
from .plugin import PluginLoader, PluginManifest

__all__ = [
    "MCPClient",
    "MCPServer", 
    "ServerConfig",
    "PluginLoader",
    "PluginManifest",
]
