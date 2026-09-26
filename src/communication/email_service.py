"""Email service for sending messages to brokers + (optional) inbound IMAP auto-replies."""
import asyncio
import aiosmtplib
import httpx
import imaplib
import os
import re
import ssl
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List, Tuple

from src.ai.message_generator import MessageGenerator
from src.database.database import db
from src.database.models import Load, Broker, Message as MessageModel
from src.utils.config import config
from src.utils.logger import logger


class EmailService:
    """Service for sending emails to brokers"""
    
    def __init__(self):
        self.settings = config.settings
        self.email_config = config.get_email_config()
        self.smtp_host = self.settings.smtp_host
        self.smtp_port = self.settings.smtp_port
        self.smtp_username = self.settings.smtp_username
        self.smtp_password = self.settings.smtp_password
        self.email_from = self.settings.email_from or self.smtp_username
        self.telegram_bot_token = self.settings.telegram_bot_token
        self.telegram_notify_chat_id = self.settings.telegram_notify_chat_id
        self.load_filtering_config = config.get_load_filtering_config()

        # Optional inbound IMAP auto-reply loop (development)
        self.imap_host = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.imap_folder = os.getenv("IMAP_FOLDER", "INBOX")
        self.imap_poll_seconds = int(os.getenv("IMAP_POLL_SECONDS", "60"))
        self.enable_imap_auto_reply = os.getenv("ENABLE_IMAP_AUTO_REPLY", "false").lower() in (
            "1",
            "true",
            "yes",
        )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False
    ) -> bool:
        """Send an email"""
        if not all([self.smtp_host, self.smtp_port, self.smtp_username, self.smtp_password]):
            logger.error("Email configuration incomplete. Cannot send email.")
            return False

        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['From'] = self.email_from
            message['To'] = to_email
            message['Subject'] = subject

            # Add body
            part = MIMEText(body, 'html' if is_html else 'plain')
            message.attach(part)

            # Send email (Gmail on port 587 uses STARTTLS)
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                start_tls=True,
            )

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False

    async def _send_telegram_notification(self, text: str) -> bool:
        """Send a Telegram message to configured notify chat."""
        token = (self.telegram_bot_token or "").strip()
        chat_id = (self.telegram_notify_chat_id or "").strip()
        if not token or not chat_id:
            logger.info("Telegram notify skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_NOTIFY_CHAT_ID missing.")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code >= 400:
                    logger.error(f"Telegram notify failed: status={resp.status_code}, body={resp.text}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Telegram notify error: {e}")
            return False

    @staticmethod
    def _norm_text(value: Optional[str]) -> str:
        return (value or "").strip().lower()

    def _passes_green_light_filter(self, load: Load) -> Tuple[bool, List[str]]:
        """Apply configured business filter to a ready load."""
        reasons: List[str] = []
        cfg = self.load_filtering_config or {}

        rate = load.rate
        commodity = self._norm_text(load.commodity)
        equipment = self._norm_text(load.equipment_type)
        miles = load.miles

        min_rate = cfg.get("min_rate", 0)
        max_rate = cfg.get("max_rate", None)
        min_miles = cfg.get("min_miles", 0)
        max_miles = cfg.get("max_miles", None)
        allowed_equipment = [self._norm_text(x) for x in (cfg.get("equipment_types") or []) if str(x).strip()]
        include_keywords = [self._norm_text(x) for x in (cfg.get("commodity_include_keywords") or []) if str(x).strip()]
        exclude_keywords = [self._norm_text(x) for x in (cfg.get("commodity_exclude_keywords") or []) if str(x).strip()]

        if rate is None:
            reasons.append("rate_missing")
        else:
            try:
                rv = float(rate)
                if min_rate is not None and rv < float(min_rate):
                    reasons.append(f"rate_below_min({rv}<{min_rate})")
                if max_rate is not None and rv > float(max_rate):
                    reasons.append(f"rate_above_max({rv}>{max_rate})")
            except Exception:
                reasons.append("rate_invalid")

        if miles is not None:
            try:
                mv = int(miles)
                if min_miles is not None and mv < int(min_miles):
                    reasons.append(f"miles_below_min({mv}<{min_miles})")
                if max_miles is not None and mv > int(max_miles):
                    reasons.append(f"miles_above_max({mv}>{max_miles})")
            except Exception:
                reasons.append("miles_invalid")

        if allowed_equipment and equipment not in allowed_equipment:
            reasons.append("equipment_not_allowed")

        if not commodity:
            reasons.append("commodity_missing")
        else:
            if include_keywords and not any(k in commodity for k in include_keywords):
                reasons.append("commodity_not_in_allowed_keywords")
            if exclude_keywords and any(k in commodity for k in exclude_keywords):
                reasons.append("commodity_in_excluded_keywords")

        return (len(reasons) == 0, reasons)

    # ---------- IMAP inbound (optional auto-reply) ----------

    def _imap_login(self) -> imaplib.IMAP4_SSL:
        """Connect and login to IMAP (synchronous)."""
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, ssl_context=context)
        mail.login(self.smtp_username, self.smtp_password)
        return mail

    @staticmethod
    def _decode_mime_header(value: str | None) -> str:
        if not value:
            return ""
        parts = decode_header(value)
        decoded = ""
        for part, enc in parts:
            if isinstance(part, bytes):
                decoded += part.decode(enc or "utf-8", errors="replace")
            else:
                decoded += str(part)
        return decoded

    @staticmethod
    def _extract_email_address(from_header: str) -> str:
        # Examples:
        #   "Name <email@domain.com>" or "email@domain.com"
        m = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", from_header or "")
        return m.group(1).lower() if m else ""

    @staticmethod
    def _extract_plain_or_html_text(msg) -> str:
        """Extract a text representation suitable for LLM extraction."""
        # Prefer text/plain
        plain_parts: List[str] = []
        html_parts: List[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disp = part.get("Content-Disposition", "")
                if "attachment" in disp.lower():
                    continue
                try:
                    payload = part.get_payload(decode=True) or b""
                except Exception:
                    payload = b""
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace") if payload else ""
                if content_type == "text/plain":
                    plain_parts.append(text)
                elif content_type == "text/html":
                    html_parts.append(text)
        else:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace") if payload else ""
            if msg.get_content_type() == "text/plain":
                plain_parts.append(text)
            else:
                html_parts.append(text)

        if plain_parts:
            # Keep only last chunk to avoid long quotes at top.
            text = "\n".join(plain_parts).strip()
            return text[-12000:] if len(text) > 12000 else text

        if html_parts:
            html = "\n".join(html_parts).strip()
            # Very light HTML stripping (enough for LLM extraction)
            html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<[^>]+>", " ", html)
            html = re.sub(r"\s+", " ", html).strip()
            return html[-12000:] if len(html) > 12000 else html

        return ""

    @staticmethod
    def _parse_subject_route(subject: str) -> Tuple[str | None, str | None]:
        """
        Parse subjects like:
          "Re: Load Inquiry - Snowville, UT to Visalia, CA"
        Returns (origin, destination) or (None,None) if it doesn't match.
        """
        s = subject or ""
        # normalize common prefixes
        s = re.sub(r"^(Re:|FW:|Fwd:)\s*", "", s, flags=re.IGNORECASE).strip()

        m = re.search(r"Load Inquiry\s*-\s*(.+?)\s*to\s*(.+)$", s, flags=re.IGNORECASE)
        if not m:
            return None, None
        origin = m.group(1).strip()
        dest = m.group(2).strip()
        return origin, dest

    @staticmethod
    def _extract_subject_load_id(subject: str) -> str | None:
        """Extract load_id token from subject, e.g. '[LID: TEST_LOAD_001]'."""
        s = subject or ""
        m = re.search(r"\[LID:\s*([^\]]+)\]", s, flags=re.IGNORECASE)
        if not m:
            return None
        value = (m.group(1) or "").strip()
        return value or None

    def _imap_fetch_unseen(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch unseen messages (synchronous)."""
        mail = self._imap_login()
        try:
            mail.select(self.imap_folder)
            typ, data = mail.search(None, "UNSEEN")
            if typ != "OK":
                return []
            ids = data[0].split() if data and data[0] else []
            ids = ids[-limit:]
            results: List[Dict[str, Any]] = []
            for msg_id in ids:
                typ, msg_data = mail.fetch(msg_id, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                # msg_data is a list of tuples (b'UID ...', raw_bytes)
                raw = None
                for part in msg_data:
                    if isinstance(part, tuple) and part[1]:
                        raw = part[1]
                        break
                if not raw:
                    continue
                msg = message_from_bytes(raw)
                from_hdr = msg.get("From", "")
                subject_hdr = msg.get("Subject", "")
                message_id_hdr = msg.get("Message-ID", "")
                in_reply_to_hdr = msg.get("In-Reply-To", "")
                references_hdr = msg.get("References", "")
                from_decoded = self._decode_mime_header(from_hdr)
                subject_decoded = self._decode_mime_header(subject_hdr)
                body_text = self._extract_plain_or_html_text(msg)

                results.append(
                    {
                        "imap_id": int(msg_id),
                        "from_header": from_decoded,
                        "from_email": self._extract_email_address(from_decoded),
                        "subject": subject_decoded,
                        "body": body_text,
                        "message_id": self._decode_mime_header(message_id_hdr),
                        "in_reply_to": self._decode_mime_header(in_reply_to_hdr),
                        "references": self._decode_mime_header(references_hdr),
                    }
                )
            return results
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    async def poll_imap_unseen_and_auto_reply(self, limit: int = 5) -> None:
        """Fetch unseen emails and generate/send follow-up emails (async wrapper)."""
        if not self.enable_imap_auto_reply:
            return
        if not self.smtp_username or not self.smtp_password:
            logger.warning("IMAP auto-reply disabled: SMTP_USERNAME/SMTP_PASSWORD missing.")
            return

        emails = await asyncio.to_thread(self._imap_fetch_unseen, limit)
        if not emails:
            return

        for mail_item in emails:
            try:
                subject = mail_item.get("subject", "")
                from_email = mail_item.get("from_email", "")
                if not from_email:
                    logger.info(f"IMAP: skipping email with missing sender: subject={subject!r}")
                    await asyncio.to_thread(self._imap_mark_seen, mail_item["imap_id"])
                    continue

                # Match strategy:
                # 1) Preferred: explicit load token in subject [LID: ...]
                # 2) Fallback: parse route from subject ("Load Inquiry - origin to destination")
                subject_load_id = self._extract_subject_load_id(subject)
                with db.get_session() as session:
                    load = None
                    if subject_load_id:
                        load = (
                            session.query(Load)
                            .filter(
                                Load.load_id == subject_load_id,
                                Load.broker_email == from_email,
                            )
                            .order_by(Load.created_at.desc())
                            .first()
                        )

                    if not load:
                        origin, destination = self._parse_subject_route(subject)
                        if origin and destination:
                            load = (
                                session.query(Load)
                                .filter(
                                    Load.origin == origin,
                                    Load.destination == destination,
                                    Load.broker_email == from_email,
                                )
                                .order_by(Load.created_at.desc())
                                .first()
                            )

                    if not load:
                        logger.info(
                            "IMAP: no matching load "
                            f"(subject_load_id={subject_load_id}, subject={subject!r}, broker={from_email})"
                        )
                        await asyncio.to_thread(self._imap_mark_seen, mail_item["imap_id"])
                        continue
                    load_id = load.load_id

                logger.info(
                    "IMAP matched email "
                    f"imap_id={mail_item.get('imap_id')} load_id={load_id} "
                    f"message_id={mail_item.get('message_id')} in_reply_to={mail_item.get('in_reply_to')}"
                )

                broker_reply_text = mail_item.get("body", "") or ""
                if not broker_reply_text.strip():
                    logger.info(f"IMAP: empty body for message {mail_item['imap_id']}, marking seen.")
                    await asyncio.to_thread(self._imap_mark_seen, mail_item["imap_id"])
                    continue

                email_service_reply = await self.reply_to_broker(load_id, broker_reply_text)
                # IMPORTANT: use `load_id` (not `load.load_id`) because `load` is detached
                # after the SQLAlchemy session context closes.
                logger.info(
                    f"IMAP auto-reply processed load={load_id} result={email_service_reply.get('success')}"
                )

                # Mark as seen after processing
                await asyncio.to_thread(self._imap_mark_seen, mail_item["imap_id"])
            except Exception as e:
                logger.error(f"IMAP auto-reply error: {e}")
                # Even on error, mark as seen to avoid infinite loops
                try:
                    await asyncio.to_thread(self._imap_mark_seen, mail_item.get("imap_id"))
                except Exception:
                    pass

    def _imap_mark_seen(self, imap_id: int) -> None:
        """Mark a message as seen (synchronous)."""
        if imap_id is None:
            return
        mail = self._imap_login()
        try:
            mail.select(self.imap_folder)
            # Gmail/GDPR: IMAP flags must use a single backslash: \Seen
            mail.store(str(imap_id), "+FLAGS", "\\Seen")
            mail.expunge()
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    async def imap_auto_reply_loop(self) -> None:
        """Run forever, periodically polling IMAP for unseen broker replies."""
        while True:
            await self.poll_imap_unseen_and_auto_reply(limit=5) # How many emails to fetch and process at once
            await asyncio.sleep(self.imap_poll_seconds) # How long to wait between polls
    
    async def send_load_inquiry(
        self,
        load_id: str,
        message_generator: Optional[MessageGenerator] = None
    ) -> Dict[str, Any]:
        """Send an inquiry message for a specific load"""
        try:
            with db.get_session() as session:
                load = session.query(Load).filter(Load.load_id == load_id).first()
                
                if not load:
                    return {'success': False, 'error': f'Load {load_id} not found'}
                
                if not load.broker_email:
                    return {'success': False, 'error': 'No broker email for this load'}
                
                # Generate message
                if not message_generator:
                    message_generator = MessageGenerator()
                
                message_body = await message_generator.generate_message_for_load(load_id)
                
                if not message_body:
                    return {'success': False, 'error': 'Could not generate message'}
                
                # Generate subject
                subject_template = self.email_config.get(
                    'subject_template',
                    'Load Inquiry - {origin} to {destination}'
                )
                base_subject = subject_template.format(
                    origin=load.origin,
                    destination=load.destination
                )
                subject = f"{base_subject} [LID: {load.load_id}]"
                
                # Send email
                success = await self.send_email(
                    to_email=load.broker_email,
                    subject=subject,
                    body=message_body
                )
                
                if success:
                    # Get or create broker
                    broker = session.query(Broker).filter(Broker.email == load.broker_email).first()
                    if not broker:
                        broker = Broker(
                            name=load.broker_name or 'Unknown',
                            email=load.broker_email,
                            phone=load.broker_phone
                        )
                        session.add(broker)
                        session.flush()
                    
                    # Create message record
                    message_record = MessageModel(
                        load_id=load.id,
                        broker_id=broker.id,
                        subject=subject,
                        body=message_body,
                        status='sent',
                        sent_at=datetime.utcnow()
                    )
                    session.add(message_record)
                    
                    # Update load status
                    load.status = 'contacted'
                    load.updated_at = datetime.utcnow()
                    
                    # Update broker last contacted
                    broker.last_contacted = datetime.utcnow()
                    
                    session.commit()
                    
                    return {
                        'success': True,
                        'email': load.broker_email,
                        'subject': subject,
                        'message_id': message_record.id
                    }
                else:
                    return {'success': False, 'error': 'Failed to send email'}
        
        except Exception as e:
            logger.error(f"Error sending load inquiry: {e}")
            return {'success': False, 'error': str(e)}

    async def reply_to_broker(
        self,
        load_id: str,
        broker_reply_text: str,
    ) -> Dict[str, Any]:
        """
        Process a broker reply and send an automatic follow-up.

        For now, the broker reply text is provided from outside (e.g. pasted via Telegram).
        This method:
          1) Updates the latest outbound Message for the load with response_text.
          2) Uses the LLM to extract rate + commodity from the broker reply.
          3) Updates Load.rate and Load.commodity if extracted.
          4) Generates a follow-up email asking only for missing fields.
          5) Sends the follow-up email and creates a new Message record.
        """
        from src.ai.llm_client import LLMClient

        try:
            with db.get_session() as session:
                load = session.query(Load).filter(Load.load_id == load_id).first()
                if not load:
                    return {"success": False, "error": f"Load {load_id} not found"}
                if not load.broker_email:
                    return {"success": False, "error": "No broker email for this load"}

                # Find broker
                broker = session.query(Broker).filter(Broker.email == load.broker_email).first()
                if not broker:
                    broker = Broker(
                        name=load.broker_name or "Unknown",
                        email=load.broker_email,
                        phone=load.broker_phone,
                        company=load.broker_name,
                    )
                    session.add(broker)
                    session.flush()

                # Update the latest message record with broker response
                latest_msg = (
                    session.query(MessageModel)
                    .filter(MessageModel.load_id == load.id)
                    .order_by(MessageModel.sent_at.desc())
                    .first()
                )
                if latest_msg:
                    latest_msg.response_text = broker_reply_text
                    latest_msg.response_received = True
                    latest_msg.response_received_at = datetime.utcnow()
                    latest_msg.status = "response_received"
                else:
                    # If we don't have an outgoing message record yet, that's still fine.
                    latest_msg = None

                # Build load details for LLM extraction/follow-up
                load_details = {
                    "load_id": load.load_id,
                    "origin": load.origin,
                    "destination": load.destination,
                    "miles": load.miles,
                    "rate": load.rate,
                    "equipment_type": load.equipment_type,
                    "pickup_date": load.pickup_date.strftime("%Y-%m-%d") if load.pickup_date else "N/A",
                    "delivery_date": load.delivery_date.strftime("%Y-%m-%d") if load.delivery_date else "N/A",
                    "weight": load.weight,
                    "commodity": load.commodity,
                }

                llm = LLMClient()

                extracted = await llm.extract_rate_and_commodity_from_reply(
                    broker_reply_text=broker_reply_text,
                    existing_load_details=load_details,
                )

                # Update DB with extracted facts if present
                extracted_rate = extracted.get("rate")
                extracted_commodity = extracted.get("commodity")

                # TODO Filter extracted commodities by logic, if ok send list of commodities to telegram
                if extracted_rate is not None:
                    load.rate = float(extracted_rate)
                if extracted_commodity is not None:
                    load.commodity = extracted_commodity

                # Determine missing fields after updates
                missing_fields: list[str] = extracted.get("missing_fields") or []
                # Recompute missing based on DB values (final truth)
                if load.rate is not None and "rate" in missing_fields:
                    missing_fields = [f for f in missing_fields if f != "rate"]
                if load.commodity is not None and "commodity" in missing_fields:
                    missing_fields = [f for f in missing_fields if f != "commodity"]

                is_ready = (load.rate is not None) and (load.commodity is not None)
                is_green_light = False
                filter_reasons: List[str] = []

                if is_ready:
                    is_green_light, filter_reasons = self._passes_green_light_filter(load)

                # Refresh load_details for follow-up
                load_details["rate"] = load.rate
                load_details["commodity"] = load.commodity

                followup_body = await llm.generate_followup_email(
                    broker_reply_text=broker_reply_text,
                    load_details=load_details,
                    missing_fields=missing_fields,
                )
                if not followup_body:
                    session.commit()
                    return {
                        "success": False,
                        "error": "LLM failed to generate follow-up email",
                        "is_ready": is_ready,
                        "extracted": extracted,
                    }

                subject_template = self.email_config.get(
                    "subject_template",
                    "Load Inquiry - {origin} to {destination}",
                )
                base_subject = subject_template.format(
                    origin=load.origin,
                    destination=load.destination,
                )
                subject = f"Re: {base_subject} [LID: {load.load_id}]"

                # Send email
                success = await self.send_email(
                    to_email=load.broker_email,
                    subject=subject,
                    body=followup_body,
                    is_html=False,
                )

                if success:
                    # Create message record for this follow-up
                    message_record = MessageModel(
                        load_id=load.id,
                        broker_id=broker.id,
                        subject=subject,
                        body=followup_body,
                        status="sent",
                        sent_at=datetime.utcnow(),
                    )
                    session.add(message_record)

                    load.status = "green_light" if is_green_light else "responded"
                    load.updated_at = datetime.utcnow()
                    broker.last_contacted = datetime.utcnow()

                # Snapshot values so we don't accidentally access lazy attributes
                # after the SQLAlchemy session scope ends.
                final_origin = load.origin
                final_destination = load.destination
                final_rate = load.rate
                final_commodity = load.commodity
                final_email = load.broker_email
                final_load_id = load.load_id

                session.commit()

                telegram_sent = False
                if is_green_light:
                    summary = (
                        "GREEN-LIGHT LOAD\n"
                        f"Load: {final_load_id}\n"
                        f"Broker: {broker.name or load.broker_name or 'Unknown'}\n"
                        f"Email: {final_email}\n"
                        f"Route: {final_origin} -> {final_destination}\n"
                        f"Commodity: {final_commodity}\n"
                        f"Rate: ${final_rate}\n"
                        f"Equipment: {load.equipment_type or 'N/A'}\n"
                        f"Miles: {load.miles if load.miles is not None else 'N/A'}"
                    )
                    telegram_sent = await self._send_telegram_notification(summary)

                return {
                    "success": bool(success),
                    "is_ready": is_ready,
                    "is_green_light": is_green_light,
                    "filter_reasons": filter_reasons,
                    "telegram_sent": telegram_sent,
                    "extracted": extracted,
                    "origin": final_origin,
                    "destination": final_destination,
                    "final_rate": final_rate,
                    "final_commodity": final_commodity,
                    "followup_subject": subject,
                    "followup_body": followup_body,
                    "email": final_email,
                    "missing_fields": missing_fields,
                }

        except Exception as e:
            logger.error(f"Error replying to broker: {e}")
            return {"success": False, "error": str(e)}
