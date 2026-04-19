"""Test normal mode - should NOT show any logs."""
from sun_cli.logging_config import get_logger

# Test main logger
main_logger = get_logger("suncli")
main_logger.debug("这是主日志器的调试信息")
main_logger.info("这是info信息")
main_logger.warning("这是warning信息")

# Test child logger
chat_logger = get_logger("sun_cli.chat")
chat_logger.debug("这是chat模块的调试信息")
chat_logger.info("这是chat的info信息")

print("\n=== 正常模式测试完成（如果上面没有任何日志输出，说明正常） ===")
