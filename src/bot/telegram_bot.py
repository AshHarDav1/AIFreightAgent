"""Telegram bot handler"""
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.utils.logger import logger
from src.utils.config import config
from src.database.database import db
from src.database.models import Load, Message as MessageModel, Broker


class TelegramBot:
    """Telegram bot for AI Freight Agent"""
    
    def __init__(self):
        self.token = config.settings.telegram_bot_token
        self.application: Optional[Application] = None
        self.is_running = False

    # ---------- Internal helpers ----------

    @staticmethod
    def _get_user_info(update: Update) -> str:
        """Return a short string identifying the user who sent the update"""
        user = update.effective_user
        if not user:
            return "unknown-user"
        username = f"@{user.username}" if user.username else f"{user.first_name or ''} {user.last_name or ''}".strip()
        return f"{username} (id={user.id})"

    def _log_command_start(self, command: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log that a command was received"""
        user_info = self._get_user_info(update)
        args = getattr(context, "args", None) or []
        logger.info(f"Command {command} received from {user_info} args={args}")

    def _log_command_success(self, command: str, update: Update, extra: str | None = None) -> None:
        """Log that a command completed successfully"""
        user_info = self._get_user_info(update)
        suffix = f" ({extra})" if extra else ""
        logger.info(f"Command {command} completed successfully for {user_info}{suffix}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        self._log_command_start("/start", update, context)

        welcome_message = (
            "🤖 <b>AI Freight Agent Bot</b>\n\n"
            "I help you manage freight loads and broker communications.\n\n"
            "<b>Available commands:</b>\n"
            "/start - Show this message\n"
            "/status - Show system status\n"
            "/stats - Show statistics\n"
            "/loads - List recent loads\n"
            "/test_scrape - Simulate scraping test data\n"
            "/generate_message &lt;load_id&gt; - Generate message for a load\n"
            "/send_message &lt;load_id&gt; - Send message to broker\n"
            "/help - Show help message"
        )
        await update.message.reply_text(welcome_message, parse_mode='HTML')
        self._log_command_success("/start", update)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        self._log_command_start("/help", update, context)

        help_text = (
            "<b>Command Help</b>\n\n"
            "/start - Start the bot\n"
            "/status - Check system status\n"
            "/stats - View statistics (loads, messages, etc.)\n"
            "/loads - List recent loads from database\n"
            "/test_scrape - Simulate scraping and add test loads\n"
            "/generate_message &lt;load_id&gt; - Generate AI message for a load\n"
            "/send_message &lt;load_id&gt; - Send email to broker for a load\n"
            "/help - Show this help"
        )
        await update.message.reply_text(help_text, parse_mode='HTML')
        self._log_command_success("/help", update)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            self._log_command_start("/status", update, context)

            with db.get_session() as session:
                total_loads = session.query(Load).count()
                new_loads = session.query(Load).filter(Load.status == 'new').count()
                contacted = session.query(Load).filter(Load.status == 'contacted').count()
                total_messages = session.query(MessageModel).count()
            
            status_text = (
                "<b>System Status</b>\n\n"
                f"📊 Total Loads: {total_loads}\n"
                f"🆕 New Loads: {new_loads}\n"
                f"📧 Contacted: {contacted}\n"
                f"✉️ Messages Sent: {total_messages}\n\n"
                f"🤖 Bot Status: {'🟢 Running' if self.is_running else '🔴 Stopped'}"
            )
            await update.message.reply_text(status_text, parse_mode='HTML')
            self._log_command_success("/status", update, extra=f"loads={total_loads}, messages={total_messages}")
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            self._log_command_start("/stats", update, context)

            with db.get_session() as session:
                total_loads = session.query(Load).count()
                total_brokers = session.query(Broker).count()
                total_messages = session.query(MessageModel).count()
                responded = session.query(MessageModel).filter(MessageModel.response_received == True).count()
                
                if total_messages > 0:
                    response_rate = (responded / total_messages) * 100
                else:
                    response_rate = 0
            
            stats_text = (
                "<b>Statistics</b>\n\n"
                f"📦 Loads: {total_loads}\n"
                f"👥 Brokers: {total_brokers}\n"
                f"✉️ Messages: {total_messages}\n"
                f"📬 Responses: {responded}\n"
                f"📈 Response Rate: {response_rate:.1f}%"
            )
            await update.message.reply_text(stats_text, parse_mode='HTML')
            self._log_command_success("/stats", update, extra=f"response_rate={response_rate:.1f}%")
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def loads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /loads command - show recent loads"""
        try:
            self._log_command_start("/loads", update, context)

            with db.get_session() as session:
                loads = session.query(Load).order_by(Load.created_at.desc()).limit(10).all()
                
                if not loads:
                    await update.message.reply_text("📭 No loads found. Use /test_scrape to add test data.")
                self._log_command_success("/loads", update, extra="no-loads")
                
                loads_text = "<b>Recent Loads</b>\n\n"
                for load in loads:
                    status_emoji = {
                        'new': '🆕',
                        'contacted': '📧',
                        'responded': '📬',
                        'booked': '✅',
                        'expired': '❌'
                    }.get(load.status, '❓')
                    
                    # Escape HTML special characters in dynamic content
                    load_id = str(load.load_id).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    origin = str(load.origin or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    destination = str(load.destination or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    status = str(load.status or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    broker_email = str(load.broker_email or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    loads_text += (
                        f"{status_emoji} <b>Load {load_id}</b>\n"
                        f"📍 {origin} → {destination}\n"
                        f"💰 ${load.rate or 'N/A'} | {load.miles or 'N/A'} miles\n"
                        f"📧 Broker Email: {broker_email}\n"
                        f"📊 Status: {status}\n\n"
                    )
                
                await update.message.reply_text(loads_text, parse_mode='HTML')
                self._log_command_success("/loads", update, extra=f"count={len(loads)}")
        except Exception as e:
            logger.error(f"Error in loads command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def test_scrape_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /test_scrape command - simulate scraping"""
        self._log_command_start("/test_scrape", update, context)

        await update.message.reply_text("🔄 Simulating scrape... This will add test loads to the database.")
        
        # Import here to avoid circular imports
        from src.scraper.test_data import TestDataSimulator
        
        try:
            simulator = TestDataSimulator()
            count = await simulator.create_test_loads()
            await update.message.reply_text(f"✅ Successfully created {count} test loads! Use /loads to view them.")
            self._log_command_success("/test_scrape", update, extra=f"created={count}")
        except Exception as e:
            logger.error(f"Error in test_scrape: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def octo_profiles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /octo_profiles - list available Octo profiles by name."""
        self._log_command_start("/octo_profiles", update, context)

        from src.octo.client import OctoClient

        client = OctoClient()
        profiles = await client.fetch_profiles()
        if not profiles:
            await update.message.reply_text(
                "❌ Could not load Octo profiles. Make sure OCTO_API_TOKEN is set."
            )
            return

        lines = ["<b>Available Octo profiles</b>:"]
        for key, profile in profiles.items():
            tags = ", ".join(profile.tags) if profile.tags else "-"
            lines.append(f"• <b>{profile.title}</b> (tags: {tags})")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        self._log_command_success("/octo_profiles", update, extra=f"count={len(profiles)}")

    async def scrape_dat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scrape_dat <profile_name> - real DAT scrape via chosen Octo profile."""
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: /scrape_dat <profile_name>\n"
                "Tip: use /octo_profiles to see available profiles."
            )
            return

        profile_name = " ".join(context.args).strip()
        self._log_command_start("/scrape_dat", update, context)

        from src.octo.client import OctoClient
        from src.scraper.dat_playwright_scraper import DATPlaywrightScraper

        client = OctoClient()
        profiles = await client.fetch_profiles(search=profile_name)
        if not profiles:
            await update.message.reply_text(
                f"❌ No Octo profiles found matching '{profile_name}'. Try /octo_profiles."
            )
            return

        # Simple matching: exact (case-insensitive) title if possible, otherwise first result.
        key = profile_name.lower()
        profile = profiles.get(key)
        if not profile:
            # fall back to first profile in the dict
            profile = next(iter(profiles.values()))

        await update.message.reply_text(
            f"🔍 Starting DAT scrape via Octo profile: <b>{profile.title}</b>",
            parse_mode="HTML",
        )

        try:
            scraper = DATPlaywrightScraper(profile_uuid=profile.uuid)
            created = await scraper.scrape_and_store()

            if created > 0:
                await update.message.reply_text(
                    f"✅ Scrape complete. {created} new loads stored. Use /loads to view them."
                )
            else:
                await update.message.reply_text(
                    "⚠️ Scrape finished but no new loads were stored.\n"
                    "Check logs, selectors, and your Octo/DAT page."
                )
            self._log_command_success(
                "/scrape_dat", update, extra=f"profile={profile.title}, created={created}"
            )
        except Exception as e:
            logger.error(f"Error in scrape_dat: {e}")
            await update.message.reply_text(f"❌ Error during DAT scrape: {str(e)}")
    
    async def generate_message_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate_message <load_id> command"""
        if not context.args:
            await update.message.reply_text("❌ Please provide a load_id. Usage: /generate_message <load_id>")
            return
        
        self._log_command_start("/generate_message", update, context)

        load_id = context.args[0]
        await update.message.reply_text(f"🤖 Generating AI message for load {load_id}...")
        
        try:
            from src.ai.message_generator import MessageGenerator
            
            generator = MessageGenerator()
            message = await generator.generate_message_for_load(load_id)
            
            if message:
                # Escape HTML in the generated message to prevent parsing errors
                escaped_message = str(message).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                await update.message.reply_text(f"✅ <b>Generated Message:</b>\n\n{escaped_message}", parse_mode='HTML')
                self._log_command_success("/generate_message", update, extra=f"load_id={load_id}")
            else:
                await update.message.reply_text(f"❌ Could not generate message for load {load_id}")
        except Exception as e:
            logger.error(f"Error generating message: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def send_message_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /send_message <load_id> command"""
        if not context.args:
            await update.message.reply_text("❌ Please provide a load_id. Usage: /send_message <load_id>")
            return
        
        self._log_command_start("/send_message", update, context)

        load_id = context.args[0]
        await update.message.reply_text(f"📧 Sending message for load {load_id}...")
        
        try:
            from src.communication.email_service import EmailService
            from src.ai.message_generator import MessageGenerator
            
            generator = MessageGenerator()
            email_service = EmailService()
            
            # Generate and send message
            result = await email_service.send_load_inquiry(load_id, generator)
            
            if result.get('success'):
                await update.message.reply_text(
                    f"✅ Message sent successfully!\n"
                    f"📧 To: {result.get('email')}\n"
                    f"📝 Subject: {result.get('subject')}"
                )
                self._log_command_success("/send_message", update, extra=f"load_id={load_id}, email={result.get('email')}")
            else:
                await update.message.reply_text(f"❌ Failed to send: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        self._log_command_start("<text>", update, context)
        await update.message.reply_text(
            "I'm a command-based bot. Use /help to see available commands."
        )
        self._log_command_success("<text>", update)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if update and update.message:
                await update.message.reply_text(
                    "❌ An error occurred. Please try again or use /help for assistance."
                )
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    def setup_handlers(self):
        """Set up command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("loads", self.loads_command))
        self.application.add_handler(CommandHandler("test_scrape", self.test_scrape_command))
        self.application.add_handler(CommandHandler("octo_profiles", self.octo_profiles_command))
        self.application.add_handler(CommandHandler("scrape_dat", self.scrape_dat_command))
        self.application.add_handler(CommandHandler("generate_message", self.generate_message_command))
        self.application.add_handler(CommandHandler("send_message", self.send_message_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
    
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
    
    async def stop(self):
        """Stop the bot"""
        if self.application:
            logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.is_running = False
            logger.info("Telegram bot stopped")
