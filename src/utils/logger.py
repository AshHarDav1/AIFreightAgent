"""Logging configuration"""
import sys
from pathlib import Path
from loguru import logger
from src.utils.config import config

# Remove default handler
logger.remove()

# Get log level from config
log_level = config.settings.log_level.upper()

# Add console handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=log_level,
    colorize=True
)

# Add file handler if log file path is configured
log_config = config.get('logging', {})
if log_config.get('file'):
    log_file = Path(log_config['file'])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation=log_config.get('max_bytes', 10485760),
        retention=log_config.get('backup_count', 5),
        compression="zip"
    )

__all__ = ['logger']
