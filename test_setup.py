"""Quick test to verify everything is set up correctly"""
import asyncio
from src.utils.logger import logger
from src.utils.config import config
from src.database.database import db
from src.bot.telegram_bot import TelegramBot


async def test_setup():
    """Test all components"""
    print("\n" + "="*60)
    print("Testing AI Freight Agent Setup")
    print("="*60)
    
    # Test 1: Configuration
    print("\n[1] Testing Configuration...")
    token = config.settings.telegram_bot_token
    if token and token != "YOUR_TOKEN_HERE":
        print(f"   ✅ Telegram token configured ({len(token)} chars)")
    else:
        print("   ❌ Telegram token not configured")
        return False
    
    # Test 2: Database
    print("\n[2] Testing Database...")
    try:
        db.create_tables()
        print("   ✅ Database initialized and tables created")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False
    
    # Test 3: Bot Creation
    print("\n[3] Testing Bot Creation...")
    try:
        bot = TelegramBot()
        if bot.token:
            print("   ✅ Bot instance created successfully")
        else:
            print("   ❌ Bot token not found")
            return False
    except Exception as e:
        print(f"   ❌ Bot creation error: {e}")
        return False
    
    # Test 4: Bot Connection (quick test)
    print("\n[4] Testing Bot Connection...")
    try:
        # Just test that we can create the application object
        from telegram import Bot
        test_bot = Bot(token=token)
        # Try to get bot info (this will verify token is valid)
        bot_info = await test_bot.get_me()
        print(f"   ✅ Bot connected! Bot name: @{bot_info.username}")
        print(f"   ✅ Bot ID: {bot_info.id}")
    except Exception as e:
        print(f"   ❌ Bot connection failed: {e}")
        print("   ⚠️  This might be a token issue. Check your token.")
        return False
    
    print("\n" + "="*60)
    print("✅ All tests passed! Ready to run the application.")
    print("="*60)
    print("\nTo start the bot, run:")
    print("  python main.py")
    print("\nThen open Telegram and send /start to your bot!")
    print("="*60 + "\n")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_setup())
    exit(0 if success else 1)
