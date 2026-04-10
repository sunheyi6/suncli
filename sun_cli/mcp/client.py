"""MCP Client - connects to external MCP servers (s19)."""

import asyncio
import json
import subprocess
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ServerConfig:
    """MCP server configuration."""
    command: str
    args: list[str]
    env: dict = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        return cls(
            command=data["command"],
            args=data.get("args", []),
            env=data.get("env"),
        )


@dataclass 
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: dict
    
    def to_agent_tool(self, server_name: str) -> dict:
        """Convert to agent tool format with prefix."""
        return {
            "name": f"mcp__{server_name}__{self.name}",
            "description": f"[{server_name}] {self.description}",
            "input_schema": self.input_schema,
        }


class MCPServer:
    """Connection to an MCP server."""
    
    def __init__(self, name: str, config: ServerConfig):
        """Initialize MCP server connection.
        
        Args:
            name: Server name
            config: Server configuration
        """
        self.name = name
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.tools: list[MCPTool] = []
        
    async def connect(self):
        """Connect to MCP server."""
        # Start server process
        env = None
        if self.config.env:
            import os
            env = {**os.environ, **self.config.env}
        
        cmd = [self.config.command] + self.config.args
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        
        # Initialize MCP protocol
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sun-cli", "version": "0.3.0"},
            }
        }
        
        self._send(init_request)
        response = self._receive()
        
        if not response or "result" not in response:
            raise RuntimeError(f"Failed to initialize MCP server {self.name}")
    
    async def list_tools(self) -> list[MCPTool]:
        """List available tools from server."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        
        self._send(request)
        response = self._receive()
        
        if not response or "result" not in response:
            return []
        
        tools_data = response["result"].get("tools", [])
        self.tools = [
            MCPTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]
        
        return self.tools
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the server.
        
        Args:
            tool_name: Tool name (without prefix)
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            }
        }
        
        self._send(request)
        response = self._receive()
        
        if not response:
            return {"error": "No response from server"}
        
        if "error" in response:
            return {"error": response["error"]}
        
        return response.get("result", {})
    
    def disconnect(self):
        """Disconnect from server."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
    
    def _send(self, message: dict):
        """Send JSON-RPC message."""
        if not self.process or self.process.stdin.closed:
            raise RuntimeError("Server not connected")
        
        data = json.dumps(message) + "\n"
        self.process.stdin.write(data)
        self.process.stdin.flush()
    
    def _receive(self) -> Optional[dict]:
        """Receive JSON-RPC response."""
        if not self.process or self.process.stdout.closed:
            return None
        
        line = self.process.stdout.readline()
        if not line:
            return None
        
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None


class MCPClient:
    """Client for managing multiple MCP servers."""
    
    def __init__(self):
        """Initialize MCP client."""
        self.servers: dict[str, MCPServer] = {}
        self._all_tools: list[dict] = []
        
    async def connect_server(self, name: str, config: ServerConfig):
        """Connect to an MCP server.
        
        Args:
            name: Server name
            config: Server configuration
        """
        server = MCPServer(name, config)
        await server.connect()
        
        # Get tools with prefixed names
        tools = await server.list_tools()
        for tool in tools:
            self._all_tools.append(tool.to_agent_tool(name))
        
        self.servers[name] = server
        
    def get_all_tools(self) -> list[dict]:
        """Get all tools from all servers with prefixed names."""
        return self._all_tools
    
    def parse_prefixed_name(self, prefixed_name: str) -> tuple[str, str]:
        """Parse mcp__server__tool into (server, tool).
        
        Args:
            prefixed_name: Prefixed tool name
            
        Returns:
            (server_name, tool_name)
        """
        parts = prefixed_name.split("__")
        if len(parts) != 3 or parts[0] != "mcp":
            raise ValueError(f"Invalid MCP tool name: {prefixed_name}")
        return parts[1], parts[2]
    
    async def call_tool(self, prefixed_name: str, arguments: dict) -> str:
        """Call an MCP tool.
        
        Args:
            prefixed_name: mcp__server__tool name
            arguments: Tool arguments
            
        Returns:
            Result as string
        """
        server_name, tool_name = self.parse_prefixed_name(prefixed_name)
        
        if server_name not in self.servers:
            return f"Error: MCP server '{server_name}' not connected"
        
        server = self.servers[server_name]
        
        try:
            result = await server.call_tool(tool_name, arguments)
            
            if "error" in result:
                return f"Error: {result['error']}"
            
            # Format result
            content = result.get("content", [])
            if content:
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "\n".join(parts)
            
            return "Tool executed successfully (no output)"
            
        except Exception as e:
            return f"Error calling MCP tool: {str(e)}"
    
    def disconnect_all(self):
        """Disconnect all servers."""
        for server in self.servers.values():
            server.disconnect()
        self.servers.clear()
