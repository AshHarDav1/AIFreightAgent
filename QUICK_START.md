# Quick Start Guide

## Prerequisites
- Python 3.10 or higher
- pip package manager
- (Optional) PostgreSQL for production use

## Setup Steps

### 1. Create Virtual Environment
```bash
cd /home/ashhardav/workspace/local/AIFreightAgent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Create a `.env` file in the project root:
```bash
# Copy the example (if available) or create manually
cat > .env << EOF
# DAT Credentials
DAT_USERNAME=your_dat_username
DAT_PASSWORD=your_dat_password

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com

# LLM API Keys (choose one or both)
OPENAI_API_KEY=sk-your_openai_key
# ANTHROPIC_API_KEY=your_anthropic_key

# Database (SQLite for development)
DATABASE_URL=sqlite:///./freight_agent.db

# Scraping Settings
SCRAPE_INTERVAL_MINUTES=30
RATE_LIMIT_DELAY_SECONDS=5

# Application Settings
LOG_LEVEL=INFO
DEBUG=false
EOF
```

### 4. Update Configuration File
Edit `config/config.yaml` with your preferences:
- Carrier information
- Message templates
- Load filtering criteria
- AI model settings

### 5. Initialize Database
```bash
python -c "from src.database.database import db; db.create_tables(); print('Database initialized!')"
```

### 6. Test Configuration
```bash
python -c "from src.utils.config import config; print('Config loaded:', config.config_path.exists())"
```

### 7. Run the Application
```bash
python main.py
```

## Development Workflow

### Testing Individual Components

**Test Database:**
```python
from src.database.database import db
from src.database.models import Load

with db.get_session() as session:
    # Test database operations
    pass
```

**Test Configuration:**
```python
from src.utils.config import config
print(config.get('scraping.interval_minutes'))
```

**Test Logging:**
```python
from src.utils.logger import logger
logger.info("Test message")
```

## Project Structure Overview

```
AIFreightAgent/
├── src/                    # Source code
│   ├── scraper/            # DAT scraping logic
│   ├── ai/                 # AI/LLM integration
│   ├── communication/      # Email/messaging
│   ├── database/           # Database models & operations
│   ├── scheduler/          # Task scheduling
│   ├── bot/               # Bot interface (optional)
│   └── utils/             # Utilities (config, logging)
├── config/                 # Configuration files
├── tests/                  # Test files
├── logs/                   # Log files (auto-created)
├── main.py                # Entry point
└── requirements.txt       # Dependencies
```

## Next Steps

1. **Implement DAT Scraper** (`src/scraper/dat_scraper.py`)
   - Research DAT website structure
   - Build scraping logic
   - Test with sample loads

2. **Implement AI Message Generation** (`src/ai/message_generator.py`)
   - Set up LLM client
   - Create message templates
   - Test message generation

3. **Implement Email Service** (`src/communication/email_service.py`)
   - Set up SMTP connection
   - Test email sending
   - Implement tracking

4. **Add Scheduler** (`src/scheduler/task_scheduler.py`)
   - Schedule scraping tasks
   - Schedule message sending
   - Monitor execution

## Troubleshooting

### Database Issues
- Ensure SQLite file permissions are correct
- Check database URL in `.env`
- Verify database tables were created

### Configuration Issues
- Verify `.env` file exists and has correct format
- Check `config/config.yaml` syntax
- Ensure all required environment variables are set

### Import Errors
- Make sure virtual environment is activated
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check Python path includes project root

### Logging Issues
- Check `logs/` directory exists and is writable
- Verify log level in configuration
- Check file permissions

## Getting Help

- Review `ARCHITECTURE.md` for system design
- Check `IMPLEMENTATION_PLAN.md` for development roadmap
- Review code comments and docstrings
- Check logs in `logs/freight_agent.log`
