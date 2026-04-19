"""Test logging configuration."""
import os

os.environ["SUN_LOG_LEVEL"] = "DEBUG"

from sun_cli.logging_config import get_logger

# Test main logger
main_logger = get_logger("suncli")
main_logger.debug("这是主日志器的调试信息")

# Test child logger
chat_logger = get_logger("sun_cli.chat")
chat_logger.debug("这是chat模块的调试信息")

# Test another child logger  
web_logger = get_logger("sun_cli.tools.web_search")
web_logger.debug("这是web_search模块的调试信息")

print("\n=== 日志配置测试完成 ===")
