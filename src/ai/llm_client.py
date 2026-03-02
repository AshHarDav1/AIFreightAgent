"""LLM client for AI integration"""
from typing import Optional, Dict, Any
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
            "You are a professional freight carrier agent. "
            "Write concise, professional, and persuasive emails to brokers about freight loads. "
            "Be friendly but business-focused. Keep messages under 200 words."
        )

        carrier = carrier_info or config.get_carrier_info()

        # Build prompt with load details
        prompt = f"""Generate a professional email message to a broker about a freight load.

Load Details:
- Origin: {load_details.get('origin', 'N/A')}
- Destination: {load_details.get('destination', 'N/A')}
- Miles: {load_details.get('miles', 'N/A')}
- Rate: ${load_details.get('rate', 'N/A')}
- Equipment Type: {load_details.get('equipment_type', 'N/A')}
- Pickup Date: {load_details.get('pickup_date', 'N/A')}

Carrier Information:
- Company: {carrier.get('name', 'Carrier Company')}
- Years of Experience: {carrier.get('years_experience', '10')}
- Equipment Available: {', '.join(carrier.get('equipment_types', []))}

Broker Name: {broker_name or 'Broker'}

Generate a professional email message that:
1. Introduces the carrier company
2. Expresses interest in the load
3. Highlights relevant capabilities
4. Requests further information or confirmation
5. Includes professional closing

Keep it concise, professional, and personalized."""

        message = await self.generate_text(prompt, system_prompt)
        return message
