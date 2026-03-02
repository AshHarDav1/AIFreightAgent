# Telegram Bot Setup & Code Explanation Guide

## Step 1: Create Your Telegram Bot

### Getting a Bot Token from BotFather

1. **Open Telegram** on your phone or desktop
2. **Search for @BotFather** in Telegram
3. **Start a chat** with BotFather
4. **Send the command**: `/newbot`
5. **Follow the prompts**:
   - BotFather will ask: "Alright, a new bot. How are we going to call it? Please choose a name for your bot."
   - **Reply with**: `AI Freight Agent Bot` (or any name you like)
   - BotFather will ask: "Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot."
   - **Reply with**: `YourNameFreightBot` (must end with "bot", e.g., `ashhardav_freight_bot`)
6. **BotFather will give you a token** that looks like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
7. **Copy this token** - you'll need it for your `.env` file

### Add Token to Your Project

1. Open or create `.env` file in your project root
2. Add this line:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
   Replace `your_token_here` with the token BotFather gave you

---

## Step 2: Understanding the Telegram Bot Code

Let me explain **every part** of the `telegram_bot.py` file:

---

## 📚 CODE EXPLANATION

### **Imports Section (Lines 1-9)**

```python
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.utils.logger import logger
from src.utils.config import config
from src.database.database import db
from src.database.models import Load, Message as MessageModel, Broker
```

**What each import does:**

1. **`asyncio`** - Python's async library. Telegram bot uses async functions (non-blocking operations)
2. **`Optional`** - Type hinting - means a variable can be None or a value
3. **`Update`** - Telegram's Update object. Contains info about incoming messages/commands
4. **`Application`** - Main bot application class from python-telegram-bot library
5. **`CommandHandler`** - Handles commands like `/start`, `/help`
6. **`MessageHandler`** - Handles regular text messages
7. **`filters`** - Filters messages (e.g., only text, only commands)
8. **`ContextTypes`** - Type hints for context object
9. **`logger`** - Our logging system
10. **`config`** - Our configuration manager
11. **`db`** - Database connection
12. **`Load, MessageModel, Broker`** - Database models

---

### **Class Definition (Lines 12-18)**

```python
class TelegramBot:
    """Telegram bot for AI Freight Agent"""
    
    def __init__(self):
        self.token = config.settings.telegram_bot_token
        self.application: Optional[Application] = None
        self.is_running = False
```

**What this does:**

- **`__init__`** - Constructor, runs when you create a TelegramBot object
- **`self.token`** - Gets the bot token from config (from .env file)
- **`self.application`** - Will hold the Telegram Application object (starts as None)
- **`self.is_running`** - Tracks if bot is running (True/False)

**Why Optional?** - Application starts as None, gets created when bot starts

---

### **Command Handlers - Part 1: start_command (Lines 20-35)**

```python
async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_message = (
        "🤖 *AI Freight Agent Bot*\n\n"
        "I help you manage freight loads and broker communications.\n\n"
        "*Available commands:*\n"
        "/start - Show this message\n"
        ...
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
```

**What this does:**

1. **`async def`** - Async function (can wait for things without blocking)
2. **`update`** - Contains the message/command from user
3. **`context`** - Extra data, like command arguments
4. **`welcome_message`** - The text to send back
5. **`*text*`** - Markdown bold (the * makes text bold in Telegram)
6. **`\n`** - New line
7. **`await update.message.reply_text(...)`** - Sends reply to user
8. **`parse_mode='Markdown'`** - Allows formatting (bold, italic, etc.)

**When user sends `/start`** → Bot sends welcome message with all commands

---

### **Command Handlers - Part 2: help_command (Lines 37-50)**

```python
async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "*Command Help*\n\n"
        "/start - Start the bot\n"
        ...
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
```

**What this does:**

- Similar to start_command
- Shows detailed help about each command
- **Purpose**: Help users understand what each command does

---

### **Command Handlers - Part 3: status_command (Lines 52-72)**

```python
async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    try:
        with db.get_session() as session:
            total_loads = session.query(Load).count()
            new_loads = session.query(Load).filter(Load.status == 'new').count()
            contacted = session.query(Load).filter(Load.status == 'contacted').count()
            total_messages = session.query(MessageModel).count()
        
        status_text = (
            "*System Status*\n\n"
            f"📊 Total Loads: {total_loads}\n"
            ...
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
```

**What this does - Line by Line:**

1. **`try:`** - Start error handling block
2. **`with db.get_session() as session:`** - Opens database connection
   - `with` ensures connection closes automatically
   - `session` is the database session object
3. **`session.query(Load).count()`** - Counts all loads in database
4. **`.filter(Load.status == 'new')`** - Filters loads where status is 'new'
5. **`f"📊 Total Loads: {total_loads}"`** - f-string formatting (inserts variable value)
6. **`except Exception as e:`** - Catches any errors
7. **`logger.error(...)`** - Logs error to file/console
8. **Sends error message to user** if something goes wrong

**Purpose**: Shows current system status (how many loads, messages, etc.)

---

### **Command Handlers - Part 4: stats_command (Lines 74-99)**

```python
async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    try:
        with db.get_session() as session:
            total_loads = session.query(Load).count()
            total_brokers = session.query(Broker).count()
            total_messages = session.query(MessageModel).count()
            responded = session.query(MessageModel).filter(MessageModel.response_received == True).count()
            
            if total_messages > 0:
                response_rate = (responded / total_messages) * 100
            else:
                response_rate = 0
```

**What this does:**

- Similar to status_command but shows more detailed statistics
- **Calculates response rate**: (responded messages / total messages) × 100
- **`if total_messages > 0:`** - Prevents division by zero error
- Shows: loads count, brokers count, messages count, response rate

**Purpose**: Shows business metrics and performance

---

### **Command Handlers - Part 5: loads_command (Lines 101-131)**

```python
async def loads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /loads command - show recent loads"""
    try:
        with db.get_session() as session:
            loads = session.query(Load).order_by(Load.created_at.desc()).limit(10).all()
            
            if not loads:
                await update.message.reply_text("📭 No loads found...")
                return
            
            loads_text = "*Recent Loads*\n\n"
            for load in loads:
                status_emoji = {
                    'new': '🆕',
                    'contacted': '📧',
                    'responded': '📬',
                    'booked': '✅',
                    'expired': '❌'
                }.get(load.status, '❓')
                
                loads_text += (
                    f"{status_emoji} *Load {load.load_id}*\n"
                    f"📍 {load.origin} → {load.destination}\n"
                    ...
                )
```

**What this does - Line by Line:**

1. **`session.query(Load)`** - Query Load table
2. **`.order_by(Load.created_at.desc())`** - Sort by creation date, newest first
3. **`.limit(10)`** - Only get 10 loads (not all)
4. **`.all()`** - Execute query and get all results
5. **`if not loads:`** - Check if list is empty
6. **`return`** - Exit function early if no loads
7. **`status_emoji = {...}.get(load.status, '❓')`** - Dictionary lookup
   - If status is 'new' → returns '🆕'
   - If status not in dict → returns '❓' (default)
8. **`loads_text += ...`** - Append to string (builds message)
9. **`f"{status_emoji} *Load {load.load_id}*\n"`** - Format string with variables

**Purpose**: Lists recent loads with their details

---

### **Command Handlers - Part 6: test_scrape_command (Lines 133-146)**

```python
async def test_scrape_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /test_scrape command - simulate scraping"""
    await update.message.reply_text("🔄 Simulating scrape...")
    
    from src.scraper.test_data import TestDataSimulator
    
    try:
        simulator = TestDataSimulator()
        count = await simulator.create_test_loads()
        await update.message.reply_text(f"✅ Successfully created {count} test loads!")
    except Exception as e:
        logger.error(f"Error in test_scrape: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
```

**What this does:**

1. **Sends immediate reply** - "Simulating scrape..." (user sees this right away)
2. **`from src.scraper.test_data import TestDataSimulator`** - Import here (not at top)
   - Why? Avoids circular imports (if imported at top, might cause issues)
3. **`simulator = TestDataSimulator()`** - Create test data simulator object
4. **`await simulator.create_test_loads()`** - Create test loads (async, so we await)
5. **`count`** - Number of loads created
6. **Sends success message** with count

**Purpose**: Creates fake/test loads for testing (without real scraping)

---

### **Command Handlers - Part 7: generate_message_command (Lines 148-169)**

```python
async def generate_message_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate_message <load_id> command"""
    if not context.args:
        await update.message.reply_text("❌ Please provide a load_id...")
        return
    
    load_id = context.args[0]
    await update.message.reply_text(f"🤖 Generating AI message for load {load_id}...")
    
    try:
        from src.ai.message_generator import MessageGenerator
        
        generator = MessageGenerator()
        message = await generator.generate_message_for_load(load_id)
        
        if message:
            await update.message.reply_text(f"✅ *Generated Message:*\n\n{message}", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Could not generate message...")
```

**What this does:**

1. **`if not context.args:`** - Check if user provided arguments
   - `/generate_message DAT123` → `context.args = ['DAT123']`
   - `/generate_message` → `context.args = []` (empty)
2. **`context.args[0]`** - Get first argument (the load_id)
3. **Sends "Generating..." message** - User sees progress
4. **Creates MessageGenerator** - Our AI message generator
5. **`await generator.generate_message_for_load(load_id)`** - Generate message using AI
6. **`if message:`** - Check if message was generated successfully
7. **Sends generated message** to user

**Purpose**: Uses AI to generate a personalized message for a specific load

---

### **Command Handlers - Part 8: send_message_command (Lines 171-200)**

```python
async def send_message_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /send_message <load_id> command"""
    if not context.args:
        await update.message.reply_text("❌ Please provide a load_id...")
        return
    
    load_id = context.args[0]
    await update.message.reply_text(f"📧 Sending message for load {load_id}...")
    
    try:
        from src.communication.email_service import EmailService
        from src.ai.message_generator import MessageGenerator
        
        generator = MessageGenerator()
        email_service = EmailService()
        
        result = await email_service.send_load_inquiry(load_id, generator)
        
        if result.get('success'):
            await update.message.reply_text(
                f"✅ Message sent successfully!\n"
                f"📧 To: {result.get('email')}\n"
                f"📝 Subject: {result.get('subject')}"
            )
        else:
            await update.message.reply_text(f"❌ Failed to send: {result.get('error')}")
```

**What this does:**

1. **Checks for load_id argument** (same as generate_message)
2. **Creates EmailService and MessageGenerator** objects
3. **`await email_service.send_load_inquiry(...)`** - Sends email to broker
4. **`result`** - Dictionary with success status, email, subject, etc.
5. **`result.get('success')`** - Check if email was sent successfully
6. **`result.get('email')`** - Get email address from result
7. **Sends success or error message** to user

**Purpose**: Actually sends email to broker (not just generate, but send)

---

### **Command Handlers - Part 9: handle_message (Lines 202-206)**

```python
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages"""
    await update.message.reply_text(
        "I'm a command-based bot. Use /help to see available commands."
    )
```

**What this does:**

- Handles **regular text messages** (not commands)
- If user sends "hello" or "hi" → bot replies with help message
- **Purpose**: Guides users to use commands instead of free text

---

### **setup_handlers Method (Lines 208-218)**

```python
def setup_handlers(self):
    """Set up command handlers"""
    self.application.add_handler(CommandHandler("start", self.start_command))
    self.application.add_handler(CommandHandler("help", self.help_command))
    self.application.add_handler(CommandHandler("status", self.status_command))
    self.application.add_handler(CommandHandler("stats", self.stats_command))
    self.application.add_handler(CommandHandler("loads", self.loads_command))
    self.application.add_handler(CommandHandler("test_scrape", self.test_scrape_command))
    self.application.add_handler(CommandHandler("generate_message", self.generate_message_command))
    self.application.add_handler(CommandHandler("send_message", self.send_message_command))
    self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
```

**What this does - Line by Line:**

1. **`CommandHandler("start", self.start_command)`** - When user sends `/start`, call `start_command` method
2. **`CommandHandler("help", self.help_command)`** - When user sends `/help`, call `help_command` method
3. **...and so on for each command**
4. **`MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)`** - Complex filter:
   - `filters.TEXT` - Only text messages
   - `~filters.COMMAND` - NOT commands (the ~ means NOT)
   - So: text messages that are NOT commands → call `handle_message`

**Purpose**: Connects Telegram commands to our Python functions

---

### **start Method (Lines 220-238)**

```python
async def start(self):
    """Start the bot"""
    if not self.token:
        logger.warning("Telegram bot token not configured. Bot will not start.")
        return
    
    try:
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        
        logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        self.is_running = True
        logger.info("Telegram bot started successfully!")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise
```

**What this does - Line by Line:**

1. **`if not self.token:`** - Check if token exists
2. **`return`** - Exit if no token (can't start bot)
3. **`Application.builder().token(self.token).build()`** - Create Telegram Application object
   - Builder pattern: chain methods to configure
   - Sets the bot token
   - Builds the application
4. **`self.setup_handlers()`** - Register all command handlers
5. **`await self.application.initialize()`** - Initialize the application
6. **`await self.application.start()`** - Start the application
7. **`await self.application.updater.start_polling()`** - Start polling for messages
   - Polling = repeatedly check Telegram for new messages
   - Alternative: webhooks (more complex, for production)
8. **`self.is_running = True`** - Mark bot as running
9. **Error handling** - If anything fails, log error and raise exception

**Purpose**: Starts the bot and makes it listen for messages

---

### **stop Method (Lines 240-248)**

```python
async def stop(self):
    """Stop the bot"""
    if self.application:
        logger.info("Stopping Telegram bot...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.is_running = False
        logger.info("Telegram bot stopped")
```

**What this does:**

1. **`if self.application:`** - Check if application exists
2. **`await self.application.updater.stop()`** - Stop polling for messages
3. **`await self.application.stop()`** - Stop the application
4. **`await self.application.shutdown()`** - Clean shutdown
5. **`self.is_running = False`** - Mark as not running

**Purpose**: Gracefully shuts down the bot (clean exit)

---

## How It All Works Together

1. **User sends `/start`** in Telegram
2. **Telegram sends message** to Telegram servers
3. **Our bot polls** Telegram servers (checks for new messages)
4. **Bot receives** the `/start` command
5. **`CommandHandler`** routes it to `start_command` method
6. **`start_command`** executes and sends reply
7. **User sees** the welcome message

---

## Next Steps

1. Get your bot token from BotFather
2. Add it to `.env` file
3. Run `python main.py`
4. Test with `/start` command in Telegram

Ready to test? Let me know when you have your token!
