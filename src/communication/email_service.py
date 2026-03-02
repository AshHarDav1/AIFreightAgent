"""Email service for sending messages to brokers"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime
from src.utils.logger import logger
from src.utils.config import config
from src.database.database import db
from src.database.models import Load, Broker, Message as MessageModel
from src.ai.message_generator import MessageGenerator


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
            
            # Send email
            # For Gmail on port 587 we should use STARTTLS (start_tls=True), not implicit TLS.
            # Implicit TLS (use_tls=True) is typically for port 465.
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
                subject = subject_template.format(
                    origin=load.origin,
                    destination=load.destination
                )
                
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
