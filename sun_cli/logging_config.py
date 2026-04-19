"""Logging configuration for Sun CLI."""

import logging
import os
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a configured logger.
    
    Args:
        name: Logger name (optional)
        
    Returns:
        Configured logger
    """
    logger_name = name or "suncli"
    logger = logging.getLogger(logger_name)
    
    # Get log level from environment variable
    log_level_str = os.environ.get("SUN_LOG_LEVEL", "CRITICAL").upper()
    
    # Only add handler and configure if DEBUG mode is explicitly enabled
    if log_level_str == "DEBUG":
        # Only configure if not already configured
        if not logger.handlers:
            log_level = getattr(logging, log_level_str, logging.CRITICAL)
            logger.setLevel(log_level)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            
            # Create formatter with Chinese-friendly format
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(formatter)
            
            # Add handler
            logger.addHandler(console_handler)
            
            # Set propagate to True to ensure child loggers work
            logger.propagate = True
        
        # Ensure all child loggers use DEBUG level
        logger.setLevel(logging.DEBUG)
    else:
        # In normal mode, disable all logging by setting to CRITICAL
        logger.setLevel(logging.CRITICAL)
        # Remove any existing handlers to ensure no output
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        logger.propagate = False
    
    return logger


logger = get_logger()
