"""LLM client for AI integration"""
import json
import re
from typing import Optional, Dict, Any, List
import asyncio

from openai import AsyncOpenAI
from groq import Groq

from src.utils.logger import logger
from src.utils.config import config


class LLMClient:
    """Client for interacting with LLM APIs (OpenAI, Groq, etc.)"""

    def __init__(self):
        self.ai_config = config.get_ai_config()

        # Provider: "openai" or "groq"
        self.provider: str = (self.ai_config.get("provider") or "openai").lower()
        self.model: str = self.ai_config.get("model", "gpt-4o-mini")
        self.temperature: float = self.ai_config.get("temperature", 0.7)
        self.max_tokens: int = self.ai_config.get("max_tokens", 500)

        self.openai_client: Optional[AsyncOpenAI] = None
        self.groq_client: Optional[Groq] = None

        if self.provider == "openai":
            api_key = config.settings.openai_api_key
            if not api_key:
                logger.warning("OpenAI API key not configured. AI features will be limited.")
            else:
                self.openai_client = AsyncOpenAI(api_key=api_key)
                logger.info(f"LLMClient initialized with OpenAI provider, model={self.model}")

        elif self.provider == "groq":
            api_key = getattr(config.settings, "groq_api_key", "")
            if not api_key:
                logger.warning("Groq API key not configured. AI features will be limited.")
            else:
                # Groq client is synchronous; we'll run it in a thread when needed
                self.groq_client = Groq(api_key=api_key)
                logger.info(f"LLMClient initialized with Groq provider, model={self.model}")
        else:
            logger.error(f"Unsupported LLM provider: {self.provider}. Supported: 'openai', 'groq'.")

    async def _generate_openai(
        self,
        messages: list[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        if not self.openai_client:
            logger.error("OpenAI client not initialized. Check OPENAI_API_KEY.")
            return None

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {e}")
            return None

    def _groq_chat_completion_sync(
        self,
        messages: list[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        """Synchronous helper to call Groq's chat API."""
        if not self.groq_client:
            logger.error("Groq client not initialized. Check GROQ_API_KEY.")
            return None
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating text with Groq: {e}")
            return None

    async def _generate_groq(
        self,
        messages: list[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        # Run synchronous Groq client in a thread to avoid blocking the event loop
        return await asyncio.to_thread(
            self._groq_chat_completion_sync,
            messages,
            temperature,
            max_tokens,
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Generate text using the configured LLM provider."""
        temp = temperature or self.temperature
        max_tok = max_tokens or self.max_tokens

        messages: list[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.provider == "openai":
            return await self._generate_openai(messages, temp, max_tok)
        elif self.provider == "groq":
            return await self._generate_groq(messages, temp, max_tok)
        else:
            logger.error(f"Cannot generate text: unsupported provider '{self.provider}'")
            return None

    async def generate_message(
        self,
        load_details: Dict[str, Any],
        broker_name: Optional[str] = None,
        carrier_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate a personalized message for a load."""
        system_prompt = (
            "You are writing the FIRST outreach email from a freight carrier to a broker.\n"
            "Write a concise, professional email body only (no subject line).\n"
            "Under 90 words.\n"
            "Use a compact block with these exact labels on separate lines:\n"
            "PU: <date>\n"
            "DELIVERY: <date>\n"
            "RATE: <amount or please confirm>\n"
            "COMMODITY: <text or please confirm>\n"
            "Do NOT include any placeholders like 'N/A' or 'MISSING'.\n"
            "If rate or commodity are missing, ask the broker to confirm ONLY those items.\n"
            "No fluff: 1 short paragraph + the block."
        )

        carrier = carrier_info or config.get_carrier_info()

        # Build prompt with load details
        rate_value = load_details.get("rate", None)
        commodity_value = load_details.get("commodity")
        rate_str = "please confirm" if rate_value is None else f"${rate_value}"
        commodity_str = "please confirm" if not commodity_value else str(commodity_value)
        pickup_date = load_details.get("pickup_date") or "N/A"
        delivery_value = load_details.get("delivery_date") or None
        delivery_str = "please confirm" if delivery_value in (None, "N/A") else str(delivery_value)
        pickup_str = "please confirm" if pickup_date == "N/A" else str(pickup_date)

        prompt = f"""Generate a professional FIRST email message to the broker.

We are looking for this exact DAT load (confirm these details):
Load ID: {load_details.get('load_id', 'N/A')}
Route: {load_details.get('origin', 'N/A')} -> {load_details.get('destination', 'N/A')}
EQUIPMENT: {load_details.get('equipment_type', 'N/A')}
PU: {pickup_str}
DELIVERY: {delivery_str}

CRITICAL:
RATE: {rate_str}
COMMODITY: {commodity_str}

In the email:
1) Use a short 1-paragraph note + the compact block exactly with labels:
PU: <date>
DELIVERY: <date>
RATE: <amount or please confirm>
COMMODITY: <text or please confirm>
2) If RATE or COMMODITY says "please confirm", ask the broker to confirm only those.
3) Short closing asking for next steps.

Return only the email body."""

        message = await self.generate_text(prompt, system_prompt)
        return message

    async def extract_rate_and_commodity_from_reply(
        self,
        broker_reply_text: str,
        existing_load_details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract rate + exact commodity from a broker reply.

        Returns JSON-like dict:
          {
            "rate": <number|null>,
            "commodity": <string|null>,
            "missing_fields": ["rate","commodity"] (subset),
            "confidence": 0..1
          }
        """
        rate_now = existing_load_details.get("rate", None)
        commodity_now = existing_load_details.get("commodity", None)

        system_prompt = (
            "You are a strict information extraction engine for freight email replies.\n"
            "Extract ONLY what is explicitly stated by the broker.\n"
            "Do NOT guess.\n"
            "Return JSON only (no markdown, no commentary)."
        )

        prompt = f"""
Broker reply (verbatim):
{broker_reply_text}

Existing known load details (may be incomplete):
- rate: {rate_now}
- commodity: {commodity_now}

Extract:
1) rate: a number (e.g., 1600) if the broker explicitly states the dollar amount for this load.
2) commodity: the exact commodity description if the broker explicitly states it.

Rules:
- If rate is not explicitly provided, rate must be null.
- If commodity is not explicitly provided, commodity must be null.
- Commodity must be SPECIFIC. Generic phrases like "general freight", "freight", "goods", "product", "stuff", "dry freight", "FAK" are NOT specific enough -> commodity must be null.
- If broker asks questions or gives only general discussion without explicit values, keep missing fields as missing.
- Use missing_fields to list which are still missing: include "rate" if rate is null; include "commodity" if commodity is null.

Return JSON with keys: rate, commodity, missing_fields, confidence.
confidence must be a number 0..1.
"""

        raw = await self.generate_text(prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=250)
        if not raw:
            missing = []
            if rate_now is None:
                missing.append("rate")
            if commodity_now is None:
                missing.append("commodity")
            return {"rate": None, "commodity": None, "missing_fields": missing, "confidence": 0.0}

        # Best-effort JSON parsing
        try:
            parsed = json.loads(raw)
        except Exception:
            # Try to extract a JSON object substring
            m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not m:
                parsed = {}
            else:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = {}

        rate = parsed.get("rate", None)
        commodity = parsed.get("commodity", None)
        missing_fields = parsed.get("missing_fields", None)
        confidence = parsed.get("confidence", None)

        # Normalize rate/commodity
        if isinstance(rate, str):
            # remove currency symbols and whitespace, keep digits + dot
            cleaned = rate.replace("$", "").replace(",", "").strip()
            try:
                rate = float(cleaned)
            except Exception:
                rate = None
        if rate is not None:
            # Convert floats like 1600.0 -> 1600
            try:
                rate = float(rate)
            except Exception:
                rate = None

        if commodity is not None and isinstance(commodity, str):
            commodity = commodity.strip()
            if not commodity:
                commodity = None

        # Reject generic/vague commodity values. We need an exact commodity.
        if commodity and isinstance(commodity, str):
            generic_terms = {
                "freight",
                "general freight",
                "general",
                "goods",
                "cargo",
                "product",
                "products",
                "stuff",
                "load",
                "dry freight",
                "fak",
                "n/a",
                "na",
                "unknown",
            }
            normalized = re.sub(r"\s+", " ", commodity.strip().lower())
            if normalized in generic_terms:
                commodity = None

        if not missing_fields or not isinstance(missing_fields, list):
            missing_fields = []
            if rate is None:
                missing_fields.append("rate")
            if commodity is None:
                missing_fields.append("commodity")
        else:
            # Keep missing_fields aligned with final normalized values.
            cleaned_missing: List[str] = []
            for fld in missing_fields:
                if isinstance(fld, str):
                    v = fld.strip().lower()
                    if v in {"rate", "commodity"} and v not in cleaned_missing:
                        cleaned_missing.append(v)
            missing_fields = cleaned_missing
            if rate is None and "rate" not in missing_fields:
                missing_fields.append("rate")
            if commodity is None and "commodity" not in missing_fields:
                missing_fields.append("commodity")
            if rate is not None:
                missing_fields = [f for f in missing_fields if f != "rate"]
            if commodity is not None:
                missing_fields = [f for f in missing_fields if f != "commodity"]

        if confidence is None:
            confidence = 0.0
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0

        return {
            "rate": rate,
            "commodity": commodity,
            "missing_fields": missing_fields,
            "confidence": confidence,
        }

    async def generate_followup_email(
        self,
        broker_reply_text: str,
        load_details: Dict[str, Any],
        missing_fields: List[str],
    ) -> Optional[str]:
        """Generate a concise follow-up email asking ONLY for missing info.

        This function is intentionally deterministic to avoid "water" and to ensure the
        broker receives only the required fields (and a fixed final close when complete).
        """
        rate_value = load_details.get("rate")
        commodity_value = load_details.get("commodity")

        # Treat explicit missing fields from extraction as authoritative.
        rate_is_missing = "rate" in (missing_fields or [])
        commodity_is_missing = "commodity" in (missing_fields or [])

        pickup_date = load_details.get("pickup_date") or "N/A"
        delivery_date = load_details.get("delivery_date") or None
        equipment_type = load_details.get("equipment_type") or "N/A"
        pickup_is_missing = pickup_date == "N/A" or not pickup_date
        delivery_is_missing = delivery_date is None or delivery_date == "N/A"

        # Final close once core required facts are present.
        # Business decision: close condition is ONLY rate + commodity.
        if not rate_is_missing and not commodity_is_missing:
            return (
                f"Thank you.\n"
                f"I'll let you know if we are doing this or not.\n\n"
                f"PU: {pickup_date}\n"
                f"DELIVERY: {delivery_date}\n"
                f"RATE: ${rate_value}\n"
                f"COMMODITY: {commodity_value}\n\n"
                f"That's it."
            )

        # If broker explicitly says unavailable/covered, do not keep asking for details.
        lower_reply = (broker_reply_text or "").strip().lower()
        unavailable_markers = [
            "not available",
            "already covered",
            "covered",
            "booked",
            "gone",
            "sold",
            "not posting",
            "no longer available",
        ]
        if any(marker in lower_reply for marker in unavailable_markers):
            return "Understood, thanks for the update."

        # Build compact convenient block with only what needs confirmation.
        rate_line = "RATE: please confirm" if rate_is_missing else f"RATE: ${rate_value}"
        commodity_line = (
            "COMMODITY: please confirm"
            if commodity_is_missing
            else f"COMMODITY: {commodity_value}"
        )

        block_lines: List[str] = [f"PU: {pickup_date if not pickup_is_missing else 'please confirm'}"]
        if not delivery_is_missing:
            block_lines.append(f"DELIVERY: {delivery_date}")
        else:
            block_lines.append("DELIVERY: please confirm")

        if equipment_type and equipment_type != "N/A":
            block_lines.append(f"EQUIPMENT: {equipment_type}")

        block_lines.append(rate_line)
        block_lines.append(commodity_line)
        load_block = "\n".join(block_lines)

        # Ask only missing items (no route/equipment/pickup repeat as questions).
        missing_questions: List[str] = []
        if rate_is_missing:
            missing_questions.append("RATE")
        if commodity_is_missing:
            missing_questions.append("COMMODITY")

        # Human-like concise ask, specific to what is missing.
        ask_lines: List[str] = []
        if rate_is_missing:
            ask_lines.append("Please send RATE (all-in USD).")
        if commodity_is_missing:
            ask_lines.append("Please send exact COMMODITY (specific item, not general freight).")
        if not ask_lines and missing_questions:
            ask_lines.append(f"Please confirm: {', '.join(missing_questions)}.")

        ask_text = "\n".join(ask_lines).strip()
        if ask_text:
            return f"{ask_text}\n\n{load_block}"
        return load_block
