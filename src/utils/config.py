"""Configuration management"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # DAT Credentials
    dat_username: str = ""
    dat_password: str = ""
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    
    # LLM API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    
    # Database
    database_url: str = "sqlite:///./freight_agent.db"
    
    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_notify_chat_id: str = ""
    
    # Scraping Settings
    scrape_interval_minutes: int = 30
    rate_limit_delay_seconds: int = 5

    # Octo Browser / DAT integration
    # Cloud API token (for listing/searching profiles)
    octo_api_token: str = os.getenv("OCTO_API_TOKEN", "")
    # Local desktop API base URL (Octo client on same host)
    # Docker containers should use host.docker.internal here.
    octo_local_api_url: str = os.getenv("OCTO_LOCAL_API_URL", "http://host.docker.internal:58888")
    octo_cloud_base_url: str = os.getenv("OCTO_CLOUD_BASE_URL", "https://app.octobrowser.net/api/v2/automation")
    # Optional CDP bridge manager URL (when app runs in Docker and needs CDP tunnel)
    # Example: http://host.docker.internal:58890
    octo_cdp_bridge_url: str = os.getenv("OCTO_CDP_BRIDGE_URL", "")
    
    # Application Settings
    log_level: str = "INFO"
    debug: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ConfigManager:
    """Manages configuration from YAML files and environment variables"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.settings = Settings()
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'scraping.interval_minutes')"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_scraping_config(self) -> Dict[str, Any]:
        """Get scraping configuration"""
        return self.config.get('scraping', {})
    
    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI configuration"""
        return self.config.get('ai', {})
    
    def get_email_config(self) -> Dict[str, Any]:
        """Get email configuration"""
        return self.config.get('email', {})
    
    def get_carrier_info(self) -> Dict[str, Any]:
        """Get carrier information"""
        return self.config.get('carrier', {})
    
    def get_message_templates(self) -> Dict[str, str]:
        """Get message templates"""
        return self.config.get('message_templates', {})

    def get_load_filtering_config(self) -> Dict[str, Any]:
        """Get load filtering criteria"""
        return self.config.get('load_filtering', {})


# Global config instance
config = ConfigManager()
