"""Telegram bot handler"""
import asyncio
import os
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
            "/possible_loads - List loads with rate + commodity\n"
            "/auto_cycle [max_scrape] [max_emails] [imap_limit] - Run scrape→send→process replies once\n"
            "/test_scrape - Simulate scraping test data\n"
            "/generate_message &lt;load_id&gt; - Generate message for a load\n"
            "/send_message &lt;load_id&gt; - Send message to broker\n"
            "/broker_reply &lt;load_id&gt; &lt;broker_reply_text&gt; - Process broker reply and auto-follow-up\n"
            "/octo_profiles - List available Octo profiles\n"
            "/scrape_dat_open &lt;profile&gt; - Open browser for manual filters\n"
            "/scrape_dat_run - Scrape visible loads (after SEARCH)\n"
            "/scrape_dat_close - Close browser session\n"
            "/scrape_dat_debug - Save page HTML for selector debugging\n"
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
            "/possible_loads - List loads that have both rate and commodity\n"
            "/auto_cycle [max_scrape] [max_emails] [imap_limit] - Run one full automated cycle\n"
            "/test_scrape - Simulate scraping and add test loads\n"
            "/generate_message &lt;load_id&gt; - Generate AI message for a load\n"
            "/send_message &lt;load_id&gt; - Send email to broker for a load\n"
            "/broker_reply &lt;load_id&gt; &lt;broker_reply_text&gt; - Process broker response and auto-reply\n"
            "/octo_profiles - List available Octo profiles\n"
            "/scrape_dat_open &lt;profile&gt; - Open Octo browser for DAT (fill filters, then SEARCH)\n"
            "/scrape_dat_run - Scrape visible loads from open session\n"
            "/scrape_dat_close - Close the scrape session\n"
            "/scrape_dat_debug - Save page HTML to debug/ for DOM inspection\n"
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
                        'green_light': '🟢',
                        'booked': '✅',
                        'expired': '❌'
                    }.get(load.status, '❓')
                    
                    # Escape HTML special characters in dynamic content
                    load_id = str(load.load_id).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    origin = str(load.origin or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    destination = str(load.destination or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    status = str(load.status or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    broker_email = str(load.broker_email or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    commodity = str(load.commodity or 'N/A').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    loads_text += (
                        f"{status_emoji} <b>Load {load_id}</b>\n"
                        f"📍 {origin} → {destination}\n"
                        f"💰 ${load.rate or 'N/A'} | {load.miles or 'N/A'} miles\n"
                        f"📦 Commodity: {commodity}\n"
                        f"📧 Broker Email: {broker_email}\n"
                        f"📊 Status: {status}\n\n"
                    )
                
                await update.message.reply_text(loads_text, parse_mode='HTML')
                self._log_command_success("/loads", update, extra=f"count={len(loads)}")
        except Exception as e:
            logger.error(f"Error in loads command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def possible_loads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /possible_loads - show loads with both rate and commodity."""
        try:
            self._log_command_start("/possible_loads", update, context)

            with db.get_session() as session:
                loads = (
                    session.query(Load)
                    .filter(Load.rate.isnot(None), Load.commodity.isnot(None))
                    .order_by(Load.updated_at.desc())
                    .limit(20)
                    .all()
                )

                if not loads:
                    await update.message.reply_text(
                        "📭 No possible loads yet. Waiting for broker replies with rate + commodity."
                    )
                    self._log_command_success("/possible_loads", update, extra="no-loads")
                    return

                text = "<b>Possible Loads (rate + commodity known)</b>\n\n"
                for load in loads:
                    load_id = str(load.load_id or "N/A").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    origin = str(load.origin or "N/A").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    destination = str(load.destination or "N/A").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    commodity = str(load.commodity or "N/A").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    broker_email = str(load.broker_email or "N/A").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    status = str(load.status or "N/A").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                    text += (
                        f"🟢 <b>{load_id}</b>\n"
                        f"📍 {origin} → {destination}\n"
                        f"💰 ${load.rate}\n"
                        f"📦 {commodity}\n"
                        f"📧 {broker_email}\n"
                        f"📊 {status}\n\n"
                    )

                await update.message.reply_text(text, parse_mode="HTML")
                self._log_command_success("/possible_loads", update, extra=f"count={len(loads)}")
        except Exception as e:
            logger.error(f"Error in possible_loads command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def auto_cycle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Run one end-to-end cycle:
          1) scrape visible DAT loads from open browser session
          2) send inquiries for up to max_emails new loads
          3) process IMAP unseen replies once
        Usage: /auto_cycle [max_scrape] [max_emails] [imap_limit]
        """
        self._log_command_start("/auto_cycle", update, context)
        max_scrape = 20
        max_emails = 20
        imap_limit = 10
        try:
            if len(context.args) >= 1:
                max_scrape = max(1, int(context.args[0]))
            if len(context.args) >= 2:
                max_emails = max(1, int(context.args[1]))
            if len(context.args) >= 3:
                imap_limit = max(1, int(context.args[2]))
        except Exception:
            await update.message.reply_text(
                "❌ Usage: /auto_cycle [max_scrape] [max_emails] [imap_limit]\n"
                "Example: /auto_cycle 20 10 15"
            )
            return

        await update.message.reply_text(
            "🔄 Running auto cycle...\n"
            f"- scrape max: {max_scrape}\n"
            f"- send max: {max_emails}\n"
            f"- IMAP limit: {imap_limit}"
        )

        try:
            from src.scraper.dat_playwright_scraper import scrape_and_store_from_open
            from src.communication.email_service import EmailService
            from src.ai.message_generator import MessageGenerator

            # 1) Scrape from currently open DAT session
            scraped_new = await scrape_and_store_from_open(max_loads=max_scrape)

            # 2) Send inquiries for newly available loads
            email_service = EmailService()
            generator = MessageGenerator()

            sent_count = 0
            send_fail_count = 0
            candidate_load_ids: list[str] = []
            with db.get_session() as session:
                candidates = (
                    session.query(Load)
                    .filter(Load.status == "new", Load.broker_email.isnot(None))
                    .order_by(Load.created_at.desc())
                    .limit(max_emails)
                    .all()
                )
                candidate_load_ids = [str(l.load_id) for l in candidates]

            for lid in candidate_load_ids:
                result = await email_service.send_load_inquiry(lid, generator)
                if result.get("success"):
                    sent_count += 1
                else:
                    send_fail_count += 1

            # 3) Process inbound IMAP replies once
            await email_service.poll_imap_unseen_and_auto_reply(limit=imap_limit)

            # Optional: snapshot ready/possible count for quick visibility
            with db.get_session() as session:
                possible_count = (
                    session.query(Load)
                    .filter(Load.rate.isnot(None), Load.commodity.isnot(None))
                    .count()
                )

            await update.message.reply_text(
                "✅ Auto cycle complete.\n"
                f"Scraped new loads: {scraped_new}\n"
                f"Inquiries sent: {sent_count}\n"
                f"Send failures: {send_fail_count}\n"
                f"Possible loads now: {possible_count}\n\n"
                "Use /possible_loads to review."
            )
            self._log_command_success(
                "/auto_cycle",
                update,
                extra=(
                    f"scraped_new={scraped_new}, sent={sent_count}, "
                    f"send_fail={send_fail_count}, possible={possible_count}"
                ),
            )
        except Exception as e:
            logger.error(f"Error in auto_cycle command: {e}")
            await update.message.reply_text(f"❌ Auto cycle failed: {str(e)}")
    
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

        # Log mapping title -> uuid to application logs
        mapping = {profile.title: profile.uuid for profile in profiles.values()}
        logger.info(f"Octo profiles mapping (title -> uuid): {mapping}")

        # Send as chunks to avoid Telegram request timeouts on larger payloads.
        # Preserve the iteration order from `profiles.values()` to keep the same order as Octo API.
        profiles_in_order = list(profiles.values())

        try:
            await update.message.reply_text("<b>Available Octo profiles</b>:", parse_mode="HTML")
        except Exception as e:
            logger.error(f"/octo_profiles failed sending header: {e!r}")
            return

        for profile in profiles_in_order:
            try:
                tags = ", ".join(profile.tags) if profile.tags else "-"
                # Keep message compact; tags can be long.
                if len(tags) > 120:
                    tags = tags[:117] + "..."

                msg = (
                    f"• <b>{profile.title}</b>\n"
                    f"  uuid: <code>{profile.uuid}</code>\n"
                    f"  tags: {tags}"
                )
                await update.message.reply_text(msg, parse_mode="HTML")
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"/octo_profiles failed sending profile chunk: {e!r}")
                continue
        self._log_command_success("/octo_profiles", update, extra=f"count={len(profiles)}")

    async def scrape_dat_open_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scrape_dat_open <profile_name> - open Octo browser for manual filters."""
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: /scrape_dat_open <profile_name>\n"
                "Tip: use /octo_profiles to see available profiles."
            )
            return

        profile_name = " ".join(context.args).strip()
        self._log_command_start("/scrape_dat_open", update, context)

        from src.octo.client import OctoClient
        from src.scraper.dat_playwright_scraper import open_for_scraping

        client = OctoClient()
        profiles = await client.fetch_profiles(search=profile_name)
        if not profiles:
            await update.message.reply_text(
                f"❌ No Octo profiles found matching '{profile_name}'. Try /octo_profiles."
            )
            return

        key = profile_name.lower()
        profile = profiles.get(key) or next(iter(profiles.values()))

        await update.message.reply_text(
            f"🔓 Opening browser for profile: <b>{profile.title}</b>...",
            parse_mode="HTML",
        )

        try:
            ok = await open_for_scraping(profile.uuid)
            if ok:
                await update.message.reply_text(
                    "✅ Browser is ready.\n\n"
                    "👉 <b>Fill filters</b> (Origin, Destination, Equipment, Date, etc.) "
                    "and click <b>SEARCH</b>.\n\n"
                    "When loads are visible, run <b>/scrape_dat_run</b> to scrape them.",
                    parse_mode="HTML",
                )
                self._log_command_success("/scrape_dat_open", update, extra=f"profile={profile.title}")
            else:
                await update.message.reply_text("❌ Failed to open browser. Check logs.")
        except Exception as e:
            logger.error(f"Error in scrape_dat_open: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def scrape_dat_run_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scrape_dat_run - scrape visible loads from the open session."""
        self._log_command_start("/scrape_dat_run", update, context)

        from src.scraper.dat_playwright_scraper import is_scrape_session_open, scrape_and_store_from_open

        if not is_scrape_session_open():
            await update.message.reply_text(
                "❌ No browser session open.\n"
                "Run <b>/scrape_dat_open</b> first, fill filters, click SEARCH, then run this again.",
                parse_mode="HTML",
            )
            return

        await update.message.reply_text("🔍 Scraping visible loads...")

        try:
            created = await scrape_and_store_from_open()
            if created > 0:
                await update.message.reply_text(
                    f"✅ Scraped {created} new loads. Use /loads to view them."
                )
            else:
                await update.message.reply_text(
                    "⚠️ No new loads stored. Make sure you clicked SEARCH and loads are visible."
                )
            self._log_command_success("/scrape_dat_run", update, extra=f"created={created}")
        except Exception as e:
            logger.error(f"Error in scrape_dat_run: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def scrape_dat_close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scrape_dat_close - close the open scrape session."""
        self._log_command_start("/scrape_dat_close", update, context)

        from src.scraper.dat_playwright_scraper import close_scrape_session

        await close_scrape_session()
        await update.message.reply_text("✅ Scrape session closed.")
        self._log_command_success("/scrape_dat_close", update)

    async def scrape_dat_debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scrape_dat_debug - save page HTML for DOM inspection."""
        self._log_command_start("/scrape_dat_debug", update, context)

        from src.scraper.dat_playwright_scraper import is_scrape_session_open, dump_page_html_for_debug

        if not is_scrape_session_open():
            await update.message.reply_text(
                "❌ No browser session open.\n"
                "Run /scrape_dat_open first, fill filters, click SEARCH so loads are visible, "
                "then run /scrape_dat_debug."
            )
            return

        path = await dump_page_html_for_debug()
        if path:
            await update.message.reply_text(
                f"✅ Page HTML saved to:\n<code>{path}</code>\n\n"
                "In Docker: the file is in <code>./debug/dat_page_debug.html</code> "
                "(project folder). Share it so we can update the load selectors.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ Failed to save page HTML. Check logs.")
        self._log_command_success("/scrape_dat_debug", update)
    
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

    async def broker_reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broker_reply <load_id> <broker_reply_text> and auto-send follow-up."""
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Usage:\n"
                "/broker_reply <load_id> <broker_reply_text>\n\n"
                "Example:\n"
                "/broker_reply 832 \"We can do $1600 for frozen chicken\""
            )
            return

        self._log_command_start("/broker_reply", update, context)

        load_id = context.args[0]
        broker_reply_text = " ".join(context.args[1:]).strip()
        if not broker_reply_text:
            await update.message.reply_text("❌ Broker reply text is empty.")
            return

        await update.message.reply_text("🤖 Processing broker reply and sending follow-up...")

        try:
            from src.communication.email_service import EmailService

            email_service = EmailService()
            result = await email_service.reply_to_broker(load_id, broker_reply_text)

            if not result.get("success"):
                await update.message.reply_text(f"❌ Failed: {result.get('error')}")
                return

            extracted = result.get("extracted") or {}
            rate = extracted.get("rate")
            commodity = extracted.get("commodity")
            missing_fields = result.get("missing_fields") or []
            is_ready = bool(result.get("is_ready"))
            is_green_light = bool(result.get("is_green_light"))
            filter_reasons = result.get("filter_reasons") or []
            telegram_sent = bool(result.get("telegram_sent"))
            origin = result.get("origin")
            destination = result.get("destination")

            if is_ready:
                rate_str = "unknown" if rate is None else f"${rate}"
                await update.message.reply_text(
                    "✅ Load is ready (rate + commodity known).\n"
                    f"Load: {load_id}\n"
                    f"Route: {origin} → {destination}\n"
                    f"Rate: {rate_str}\n"
                    f"Commodity: {commodity}"
                )
            else:
                await update.message.reply_text(
                    "✅ Extracted from broker reply, follow-up sent.\n"
                    f"Load: {load_id}\n"
                    f"Route: {origin} → {destination}\n"
                    f"Rate: {'unknown' if rate is None else f'${rate}'}\n"
                    f"Commodity: {commodity if commodity else 'unknown'}\n"
                    f"Missing: {', '.join(missing_fields) if missing_fields else 'unknown'}"
                )

            if is_green_light:
                await update.message.reply_text(
                    "🟢 Green-light match passed filters.\n"
                    f"Telegram notified: {'yes' if telegram_sent else 'no'}"
                )
            elif is_ready and filter_reasons:
                await update.message.reply_text(
                    "🟡 Ready but not green-light (filter mismatch).\n"
                    f"Reasons: {', '.join(filter_reasons)}"
                )

            self._log_command_success(
                "/broker_reply",
                update,
                extra=f"is_ready={is_ready}, missing={missing_fields}",
            )
        except Exception as e:
            logger.error(f"Error in broker_reply: {e}")
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
        err = getattr(context, "error", None)
        logger.error(
            f"Update {update} caused error {err!r} (type={type(err).__name__ if err else None})"
        )
        
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
        self.application.add_handler(CommandHandler("possible_loads", self.possible_loads_command))
        self.application.add_handler(CommandHandler("auto_cycle", self.auto_cycle_command))
        self.application.add_handler(CommandHandler("test_scrape", self.test_scrape_command))
        self.application.add_handler(CommandHandler("octo_profiles", self.octo_profiles_command))
        self.application.add_handler(CommandHandler("scrape_dat_open", self.scrape_dat_open_command))
        self.application.add_handler(CommandHandler("scrape_dat_run", self.scrape_dat_run_command))
        self.application.add_handler(CommandHandler("scrape_dat_close", self.scrape_dat_close_command))
        self.application.add_handler(CommandHandler("scrape_dat_debug", self.scrape_dat_debug_command))
        self.application.add_handler(CommandHandler("generate_message", self.generate_message_command))
        self.application.add_handler(CommandHandler("send_message", self.send_message_command))
        self.application.add_handler(CommandHandler("broker_reply", self.broker_reply_command))
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

            # Optional: IMAP auto-reply loop (infinite background task)
            try:
                from src.communication.email_service import EmailService

                email_service = EmailService()
                if getattr(email_service, "enable_imap_auto_reply", False):
                    asyncio.create_task(email_service.imap_auto_reply_loop())
                    logger.info("IMAP auto-reply loop started.")
                else:
                    logger.info("IMAP auto-reply loop disabled (ENABLE_IMAP_AUTO_REPLY=false).")
            except Exception as e:
                logger.error(f"Failed to start IMAP auto-reply loop: {e!r}")
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
