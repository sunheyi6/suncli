"""Test normal mode - should NOT show any logs."""
from sun_cli.logging_config import get_logger

logger = get_logger()
logger.debug("这条debug信息不应该显示")
logger.info("这条info信息不应该显示")
logger.warning("这条warning信息不应该显示")

logger2 = get_logger("sun_cli.chat")
logger2.debug("chat模块的debug日志也不应该显示")

print("=== 正常模式测试完成（如果上面没有任何日志输出，说明正常） ===")
