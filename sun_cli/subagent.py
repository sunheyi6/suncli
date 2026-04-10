"""Subagent system - spawn isolated agents for subtasks (s04)."""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .tools import ToolResult
from .tools.executor import ToolCallParser, ToolExecutor, ToolCall


@dataclass
class SubagentResult:
    """Result from subagent execution."""
    success: bool
    summary: str
    iterations: int
    tool_calls: list[str] = field(default_factory=list)


class SubagentRunner:
    """Runs a subagent with fresh context for isolated subtasks."""
    
    # Subagent system prompt - shorter, focused on the task
    SUBAGENT_SYSTEM = """You are a subagent working on a specific subtask.
Your job is to complete the assigned task efficiently using available tools.

Guidelines:
1. Focus ONLY on the specific subtask you were given
2. Use tools to gather information and make changes
3. When done, provide a clear summary of what you found or did
4. Do NOT ask clarifying questions - do your best with available information
5. Be thorough but concise

When finished, end with a summary paragraph starting with "SUMMARY:"."""
    
    def __init__(self, client: httpx.AsyncClient, config: Any):
        """Initialize subagent runner.
        
        Args:
            client: HTTP client for API calls
            config: Configuration with model, base_url, etc.
        """
        self.client = client
        self.config = config
        
    async def run(
        self, 
        prompt: str, 
        tools: list[str] = None,
        max_iterations: int = 30,
    ) -> SubagentResult:
        """Run a subagent with fresh context.
        
        Args:
            prompt: The task for the subagent
            tools: List of allowed tools (default: read, bash)
            max_iterations: Safety limit for tool calls
            
        Returns:
            SubagentResult with summary
        """
        # Fresh messages - no parent context
        messages = [
            {"role": "system", "content": self.SUBAGENT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        
        allowed_tools = tools or ["read", "bash"]
        tool_calls_made = []
        
        for iteration in range(max_iterations):
            # Call LLM
            response = await self._call_llm(messages, allowed_tools)
            
            if not response:
                return SubagentResult(
                    success=False,
                    summary="Failed to get response from LLM",
                    iterations=iteration,
                    tool_calls=tool_calls_made,
                )
            
            # Check for tool calls
            tool_calls = ToolCallParser.parse(response)
            
            if not tool_calls:
                # No tool calls - subagent is done
                summary = self._extract_summary(response)
                return SubagentResult(
                    success=True,
                    summary=summary,
                    iterations=iteration + 1,
                    tool_calls=tool_calls_made,
                )
            
            # Execute tool calls
            messages.append({"role": "assistant", "content": response})
            
            results = []
            for call in tool_calls:
                # Filter to allowed tools
                if call.name not in allowed_tools:
                    result = f"Error: Tool '{call.name}' not allowed. Allowed: {allowed_tools}"
                else:
                    result = ToolExecutor.execute(call)
                    tool_calls_made.append(call.to_string())
                
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result if isinstance(result, str) else str(result),
                })
            
            messages.append({"role": "user", "content": json.dumps(results)})
        
        # Max iterations reached
        return SubagentResult(
            success=False,
            summary=f"Max iterations ({max_iterations}) reached. Task incomplete.",
            iterations=max_iterations,
            tool_calls=tool_calls_made,
        )
    
    async def _call_llm(self, messages: list[dict], tools: list[str]) -> Optional[str]:
        """Call LLM with messages."""
        try:
            # Build tool definitions for subagent
            from .tools.definitions import ALL_TOOLS
            
            tool_schemas = []
            for tool in ALL_TOOLS:
                if tool.name in tools:
                    tool_schemas.append(tool.to_schema())
            
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "tools": tool_schemas if tool_schemas else None,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception:
            return None
    
    def _extract_summary(self, text: str) -> str:
        """Extract summary from subagent response."""
        # Look for SUMMARY: marker
        if "SUMMARY:" in text:
            parts = text.split("SUMMARY:", 1)
            return parts[1].strip()
        
        # Otherwise return last paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[-1]
        
        return text


async def run_subagent(
    client: httpx.AsyncClient,
    config: Any,
    prompt: str,
    tools: list[str] = None,
) -> str:
    """Convenience function to run a subagent and return summary.
    
    Args:
        client: HTTP client
        config: Configuration
        prompt: Task prompt
        tools: Allowed tools
        
    Returns:
        Summary string
    """
    runner = SubagentRunner(client, config)
    result = await runner.run(prompt, tools)
    return result.summary
