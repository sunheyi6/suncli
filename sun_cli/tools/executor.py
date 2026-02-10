"""Tool calling parser for Sun CLI."""

import json
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
from . import read_file, write_file, edit_file, run_bash


@dataclass
class ToolCall:
    """Represents a tool call."""
    name: str
    args: Dict[str, Any]
    
    def to_string(self) -> str:
        """Convert tool call to string representation."""
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in self.args.items())
        return f"{self.name}({args_str})"


class ToolCallParser:
    """Parse tool calls from AI response."""
    
    # Pattern for XML-style tool calls
    XML_PATTERN = re.compile(
        r'<tool\s+name="([^"]+)">\s*(.*?)\s*</tool>',
        re.DOTALL
    )
    
    # Pattern for JSON-style tool calls
    JSON_PATTERN = re.compile(
        r'\{?\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"args"\s*:\s*(\{.*?\})\s*\}?',
        re.DOTALL
    )
    
    @classmethod
    def parse(cls, text: str) -> list[ToolCall]:
        """Parse tool calls from text.
        
        Supports two formats:
        1. XML: <tool name="read"><arg name="file_path">test.txt</arg></tool>
        2. JSON: ```json{"tool": "read", "args": {"file_path": "test.txt"}}```
        
        Returns:
            List of ToolCall objects
        """
        calls = []
        
        # Try XML format first
        for match in cls.XML_PATTERN.finditer(text):
            name = match.group(1)
            args_text = match.group(2)
            args = cls._parse_args(args_text)
            calls.append(ToolCall(name=name, args=args))
        
        # Try JSON format
        for match in cls.JSON_PATTERN.finditer(text):
            name = match.group(1)
            args_text = match.group(2)
            try:
                args = json.loads(args_text)
                calls.append(ToolCall(name=name, args=args))
            except json.JSONDecodeError:
                continue
        
        return calls
    
    @classmethod
    def _parse_args(cls, args_text: str) -> Dict[str, Any]:
        """Parse arguments from XML format.
        
        Example:
            <arg name="file_path">test.txt</arg>
            <arg name="content">Hello</arg>
        """
        args = {}
        arg_pattern = re.compile(r'<arg\s+name="([^"]+)">\s*(.*?)\s*</arg>', re.DOTALL)
        
        for match in arg_pattern.finditer(args_text):
            name = match.group(1)
            value = match.group(2).strip()
            
            # Try to parse as JSON for complex types
            try:
                args[name] = json.loads(value)
            except json.JSONDecodeError:
                args[name] = value
        
        return args
    
    @classmethod
    def has_tool_calls(cls, text: str) -> bool:
        """Check if text contains tool calls."""
        return bool(cls.XML_PATTERN.search(text) or cls.JSON_PATTERN.search(text))


class ToolExecutor:
    """Execute tool calls."""
    
    TOOL_MAP = {
        "read": read_file,
        "write": write_file,
        "edit": edit_file,
        "bash": run_bash,
    }
    
    @classmethod
    def execute(cls, call: ToolCall) -> str:
        """Execute a tool call.
        
        Args:
            call: ToolCall to execute
            
        Returns:
            Result string
        """
        tool_func = cls.TOOL_MAP.get(call.name)
        
        if not tool_func:
            return f"Error: Unknown tool '{call.name}'. Available tools: {list(cls.TOOL_MAP.keys())}"
        
        try:
            result = tool_func(**call.args)
            
            if result.success:
                return result.content
            else:
                return f"Error: {result.error}"
        except Exception as e:
            return f"Error executing tool: {str(e)}"
    
    @classmethod
    def execute_all(cls, calls: list[ToolCall]) -> list[str]:
        """Execute multiple tool calls.
        
        Args:
            calls: List of ToolCall objects
            
        Returns:
            List of result strings
        """
        return [cls.execute(call) for call in calls]
