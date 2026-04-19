"""Test debug mode - should show all logs."""
import os

# Enable debug mode
os.environ["SUN_LOG_LEVEL"] = "DEBUG"

from sun_cli.logging_config import get_logger

# Get logger and test
logger = get_logger()
logger.debug("=== Debug模式测试 ===")
logger.debug("这条debug信息应该显示")
logger.info("这条info信息应该显示")
logger.warning("这条warning信息应该显示")

# Test getting the logger multiple times (should use cache)
logger2 = get_logger("sun_cli.chat")
logger2.debug("这是chat模块的日志")

print("\n=== 测试完成 ===")
