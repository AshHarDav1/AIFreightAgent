"""Test script to verify the complete flow"""
import asyncio
from src.utils.logger import logger
from src.database.database import db
from src.scraper.test_data import TestDataSimulator
from src.ai.message_generator import MessageGenerator
from src.communication.email_service import EmailService


async def test_complete_flow():
    """Test the complete flow: scrape -> generate -> send"""
    logger.info("=" * 60)
    logger.info("Testing Complete Flow")
    logger.info("=" * 60)
    
    # Initialize database
    db.create_tables()
    logger.info("✓ Database initialized")
    
    # Step 1: Create test loads
    logger.info("\n[Step 1] Creating test loads...")
    simulator = TestDataSimulator()
    count = await simulator.create_test_loads(count=3)
    logger.info(f"✓ Created {count} test loads")
    
    # Step 2: List loads
    logger.info("\n[Step 2] Listing loads...")
    from src.database.models import Load
    with db.get_session() as session:
        loads = session.query(Load).filter(Load.status == 'new').limit(3).all()
        for load in loads:
            logger.info(f"  - Load {load.load_id}: {load.origin} → {load.destination} "
                       f"(${load.rate}, {load.miles} miles)")
    
    if not loads:
        logger.error("No loads found. Cannot continue test.")
        return
    
    # Step 3: Generate message for first load
    logger.info("\n[Step 3] Generating AI message...")
    generator = MessageGenerator()
    test_load = loads[0]
    message = await generator.generate_message_for_load(test_load.load_id)
    
    if message:
        logger.info(f"✓ Generated message for load {test_load.load_id}")
        logger.info(f"\nGenerated Message Preview (first 200 chars):")
        logger.info("-" * 60)
        logger.info(message[:200] + "..." if len(message) > 200 else message)
        logger.info("-" * 60)
    else:
        logger.warning("⚠ Could not generate message (API key may not be configured)")
        logger.info("This is expected if OpenAI API key is not set in .env")
    
    # Step 4: Test email sending (dry run - won't actually send if email not configured)
    logger.info("\n[Step 4] Testing email service...")
    email_service = EmailService()
    
    if email_service.smtp_username and email_service.smtp_password:
        logger.info("Email credentials found. Would send email in production.")
        logger.info(f"Would send to: {test_load.broker_email}")
        logger.info("⚠ Skipping actual email send in test mode")
    else:
        logger.warning("⚠ Email credentials not configured. Skipping email test.")
        logger.info("To test email sending, configure SMTP settings in .env")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    logger.info(f"✓ Test loads created: {count}")
    logger.info(f"✓ Message generation: {'✓ Working' if message else '⚠ API key needed'}")
    logger.info(f"✓ Email service: {'✓ Configured' if email_service.smtp_username else '⚠ Needs configuration'}")
    logger.info("\nTo test with Telegram bot:")
    logger.info("1. Set TELEGRAM_BOT_TOKEN in .env")
    logger.info("2. Run: python main.py")
    logger.info("3. Use /test_scrape, /loads, /generate_message, /send_message commands")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
