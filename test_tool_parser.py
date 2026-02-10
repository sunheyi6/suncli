from sun_cli.tools.executor import ToolCallParser, ToolExecutor

# Test XML format
text1 = '<tool name="read"><arg name="file_path">test.txt</arg></tool>'
calls1 = ToolCallParser.parse(text1)
print('XML Parsed:', calls1)

# Test JSON format
text2 = '{"tool": "read", "args": {"file_path": "test.txt"}}'
calls2 = ToolCallParser.parse(text2)
print('JSON Parsed:', calls2)

# Test has_tool_calls
print('Has tool calls (XML):', ToolCallParser.has_tool_calls(text1))
print('Has tool calls (JSON):', ToolCallParser.has_tool_calls(text2))
print('Has tool calls (plain):', ToolCallParser.has_tool_calls('Hello world'))

# Test multiple tool calls
text3 = '''<tool name="read">
  <arg name="file_path">README.md</arg>
</tool>

<tool name="bash">
  <arg name="command">ls -la</arg>
</tool>'''
calls3 = ToolCallParser.parse(text3)
print('Multiple calls:', calls3)
