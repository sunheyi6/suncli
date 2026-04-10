"""Plugin system - load .claude-plugin directories (s19)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .client import MCPClient, ServerConfig


@dataclass
class PluginManifest:
    """Plugin manifest."""
    name: str
    version: str
    description: str
    mcp_servers: dict[str, ServerConfig]
    
    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        servers = {
            name: ServerConfig.from_dict(config)
            for name, config in data.get("mcpServers", {}).items()
        }
        return cls(
            name=data["name"],
            version=data.get("version", "0.0.1"),
            description=data.get("description", ""),
            mcp_servers=servers,
        )


class PluginLoader:
    """Loads plugins from .claude-plugin directories."""
    
    PLUGIN_DIR_NAME = ".claude-plugin"
    MANIFEST_NAME = "plugin.json"
    
    def __init__(self, root: Path = None):
        """Initialize plugin loader.
        
        Args:
            root: Project root to search for plugins
        """
        if root is None:
            root = Path.cwd()
        self.root = Path(root).resolve()
        self._plugins: list[PluginManifest] = []
        
    def discover(self) -> list[Path]:
        """Discover all plugin directories.
        
        Returns:
            List of plugin directory paths
        """
        plugins = []
        
        # Check root
        root_plugin = self.root / self.PLUGIN_DIR_NAME
        if root_plugin.exists():
            plugins.append(root_plugin)
        
        # Check subdirectories
        for subdir in self.root.iterdir():
            if subdir.is_dir():
                plugin_dir = subdir / self.PLUGIN_DIR_NAME
                if plugin_dir.exists():
                    plugins.append(plugin_dir)
        
        return plugins
    
    def load(self, plugin_dir: Path) -> Optional[PluginManifest]:
        """Load a single plugin.
        
        Args:
            plugin_dir: Plugin directory path
            
        Returns:
            Plugin manifest or None if invalid
        """
        manifest_path = plugin_dir / self.MANIFEST_NAME
        
        if not manifest_path.exists():
            return None
        
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return PluginManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading plugin from {plugin_dir}: {e}")
            return None
    
    def load_all(self) -> list[PluginManifest]:
        """Load all discovered plugins.
        
        Returns:
            List of loaded manifests
        """
        self._plugins = []
        
        for plugin_dir in self.discover():
            manifest = self.load(plugin_dir)
            if manifest:
                self._plugins.append(manifest)
        
        return self._plugins
    
    async def connect_plugins(self, mcp_client: MCPClient):
        """Connect all plugins to MCP client.
        
        Args:
            mcp_client: MCP client to connect servers to
        """
        for plugin in self._plugins:
            for name, config in plugin.mcp_servers.items():
                try:
                    await mcp_client.connect_server(name, config)
                    print(f"Connected MCP server: {name} (from {plugin.name})")
                except Exception as e:
                    print(f"Failed to connect MCP server {name}: {e}")
    
    def get_all_tools(self) -> list[dict]:
        """Get tool definitions from all plugins for display.
        
        Returns:
            List of tool info dicts
        """
        tools = []
        for plugin in self._plugins:
            for name, config in plugin.mcp_servers.items():
                tools.append({
                    "plugin": plugin.name,
                    "server": name,
                    "command": config.command,
                    "args": config.args,
                })
        return tools
