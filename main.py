"""Main entry point for AI Freight Agent"""
import asyncio
import signal
from src.utils.logger import logger
from src.utils.config import config
from src.database.database import db
from src.bot.telegram_bot import TelegramBot


class AIFreightAgent:
    """Main application class"""
    
    def __init__(self):
        self.bot: TelegramBot = None
        self.running = False
    
    async def initialize(self):
        """Initialize all components"""
        logger.info("Starting AI Freight Agent...")
        logger.info(f"Configuration loaded from {config.config_path}")
        
        # Initialize database
        db.create_tables()
        logger.info("Database initialized")
        
        # Initialize Telegram bot
        self.bot = TelegramBot()
        if self.bot.token:
            try:
                await self.bot.start()
                logger.info("Telegram bot started successfully")
            except Exception as e:
                logger.error(f"Failed to start Telegram bot: {e}")
                logger.warning("Continuing without Telegram bot...")
        else:
            logger.warning("Telegram bot token not configured. Bot disabled.")
    
    async def shutdown(self):
        """Shutdown all components"""
        logger.info("Shutting down AI Freight Agent...")
        
        if self.bot:
            try:
                await self.bot.stop()
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")
        
        self.running = False
        logger.info("Shutdown complete")
    
    async def run(self):
        """Run the main application loop"""
        await self.initialize()
        self.running = True
        
        logger.info("=" * 50)
        logger.info("AI Freight Agent is ready!")
        logger.info("=" * 50)
        logger.info("Telegram bot commands:")
        logger.info("  /start - Start the bot")
        logger.info("  /help - Show help")
        logger.info("  /test_scrape - Create test loads")
        logger.info("  /loads - List loads")
        logger.info("  /generate_message <load_id> - Generate AI message")
        logger.info("  /send_message <load_id> - Send message to broker")
        logger.info("=" * 50)
        logger.info("Press Ctrl+C to stop")
        
        # Set up signal handlers (Unix only)
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
                except (NotImplementedError, ValueError, RuntimeError):
                    # Signal handlers not available on this platform
                    pass
        except (NotImplementedError, AttributeError, RuntimeError):
            # Signal handlers not available on this platform
            pass
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.shutdown()


async def main():
    """Main entry point"""
    app = AIFreightAgent()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated")
