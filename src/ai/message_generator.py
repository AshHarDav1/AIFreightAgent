"""AI message generator"""
from typing import Optional, Dict, Any
from src.utils.logger import logger
from src.database.database import db
from src.database.models import Load, Broker
from src.ai.llm_client import LLMClient
from src.utils.config import config


class MessageGenerator:
    """Generates AI-powered messages for loads"""
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.templates = config.get_message_templates()
        self.carrier_info = config.get_carrier_info()
    
    async def generate_message_for_load(self, load_id: str) -> Optional[str]:
        """Generate a message for a specific load"""
        try:
            with db.get_session() as session:
                load = session.query(Load).filter(Load.load_id == load_id).first()
                
                if not load:
                    logger.error(f"Load {load_id} not found")
                    return None
                
                # Get or create broker
                broker = None
                if load.broker_email:
                    broker = session.query(Broker).filter(Broker.email == load.broker_email).first()
                    if not broker and load.broker_name:
                        # Create broker if doesn't exist
                        broker = Broker(
                            name=load.broker_name,
                            email=load.broker_email,
                            phone=load.broker_phone,
                            company=load.broker_name
                        )
                        session.add(broker)
                        session.commit()
                
                # Prepare load details
                load_details = {
                    'load_id': load.load_id,
                    'origin': load.origin,
                    'destination': load.destination,
                    'miles': load.miles,
                    'rate': load.rate,
                    'equipment_type': load.equipment_type,
                    'pickup_date': load.pickup_date.strftime('%Y-%m-%d') if load.pickup_date else 'N/A',
                    'delivery_date': load.delivery_date.strftime('%Y-%m-%d') if load.delivery_date else 'N/A',
                    'weight': load.weight,
                    'commodity': load.commodity
                }
                
                # Generate message using LLM
                message = await self.llm_client.generate_message(
                    load_details=load_details,
                    broker_name=broker.name if broker else load.broker_name,
                    carrier_info=self.carrier_info
                )
                
                if message:
                    logger.info(f"Generated message for load {load_id}")
                    return message
                else:
                    # Fallback to template-based message
                    return self._generate_template_message(load_details, broker)
        
        except Exception as e:
            logger.error(f"Error generating message for load {load_id}: {e}")
            return None
    
    def _generate_template_message(self, load_details: Dict[str, Any], broker: Optional[Broker]) -> str:
        """Generate message using templates (fallback)"""
        greeting = self.templates.get("greeting", "Hello {broker_name},").format(
            broker_name=broker.name if broker else "Broker"
        )

        # "First message" fallback: concise and explicitly includes rate + exact commodity.
        rate = load_details.get("rate")
        rate_str = f"${rate}" if rate is not None else "please confirm"
        commodity = load_details.get("commodity") or "N/A"
        if commodity == "N/A":
            commodity = "please confirm"
        pickup_date = load_details.get("pickup_date") or "N/A"
        equipment_type = load_details.get("equipment_type") or "N/A"

        load_line = (
            "DAT load:\n"
            f"Route: {load_details.get('origin', 'N/A')} -> {load_details.get('destination', 'N/A')}\n"
            f"EQUIPMENT: {equipment_type}\n"
            f"PU: {pickup_date}\n"
            f"RATE: {rate_str}\n"
            f"COMMODITY: {commodity}"
        )

        closing = self.templates.get(
            "closing",
            "Please confirm availability plus the RATE and COMMODITY above.",
        )
        signature = self.templates.get("signature", "").format(
            agent_name=self.carrier_info.get("agent_name", "AI Agent"),
            carrier_name=self.carrier_info.get("name", "Carrier Company"),
            contact_info=self.carrier_info.get("contact_info", ""),
        )

        # If signature template is empty/misconfigured, still provide a usable end.
        if not signature.strip():
            signature = (
                f"Best regards,\n{self.carrier_info.get('agent_name', 'AI Agent')}\n"
                f"{self.carrier_info.get('name', 'Carrier Company')}"
            )

        return "\n\n".join([greeting, load_line, closing, signature])
