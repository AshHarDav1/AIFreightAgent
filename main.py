"""Main entry point for AI Freight Agent"""
import asyncio
from src.utils.logger import logger
from src.utils.config import config
from src.database.database import db


async def main():
    """Main application entry point"""
    logger.info("Starting AI Freight Agent...")
    logger.info(f"Configuration loaded from {config.config_path}")
    
    # Initialize database
    db.create_tables()
    logger.info("Database initialized")
    
    # TODO: Initialize and start components
    # - Scraper
    # - AI service
    # - Email service
    # - Scheduler
    # - Bot (optional)
    
    logger.info("AI Freight Agent is ready!")
    logger.info("Press Ctrl+C to stop")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
