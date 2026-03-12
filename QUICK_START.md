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

## Docker + Octo Bridge Setup (DAT Scraping)

Use this when you run the app in Docker but Octo Browser runs on the host.

### 1. Requirements
- Docker + docker-compose
- Octo Browser running on the host (local API on `127.0.0.1:58888`)
- Optional but recommended: `ufw` firewall enabled

### 2. Start the Octo HTTP bridge (host)
On the machine where Octo is running:

```bash
cd /home/ashot/Documents/AIFreightAgent
chmod +x scripts/octo-bridge.sh
./scripts/octo-bridge.sh
```

This exposes `0.0.0.0:58889 -> 127.0.0.1:58888` using `socat`. Keep this terminal running.

### 3. Start the Octo CDP bridge manager (host)

In a second terminal on the same host:

```bash
cd /home/ashot/Documents/AIFreightAgent
python scripts/octo-cdp-bridge-manager.py
```

This starts an HTTP server on `0.0.0.0:58890` and will open CDP bridges on ports `60000–60100`.

### 4. Find your Docker subnet

```bash
docker network ls
docker network inspect aifreightagent_default | grep -A5 '"IPAM"'
# or, for the default bridge:
docker network inspect bridge | grep -A5 '"IPAM"'
```

Note the `Subnet` value (for example `172.18.0.0/16`).

### 5. Check and open firewall ports (host)

Check current rules:

```bash
sudo ufw status numbered
```

If needed, allow the Docker subnet to reach just the bridge ports (replace `172.18.0.0/16` with your subnet):

```bash
sudo ufw allow from 172.18.0.0/16 to any port 58889 proto tcp
sudo ufw allow from 172.18.0.0/16 to any port 58890 proto tcp
sudo ufw allow from 172.18.0.0/16 to any port 60000:60100 proto tcp
sudo ufw reload
```

Do **not** open these ports to the whole internet.

### 6. Configure `.env` for Docker

In your project `.env`:

```env
OCTO_LOCAL_API_URL=http://host.docker.internal:58889
OCTO_CDP_BRIDGE_URL=http://host.docker.internal:58890
```

### 7. Run the app in Docker

From the project root:

```bash
docker-compose up --build
```

### 8. Scrape DAT via Telegram bot

From Telegram:

1. `/octo_profiles` – list Octo profiles and pick a name.
2. `/scrape_dat_open <profile_name>` – starts the profile and attaches Playwright.
3. In the Octo browser window, go to **Search Loads**, set filters, and click **SEARCH**.
4. `/scrape_dat_run` – scrapes the visible loads into the database.
5. `/scrape_dat_close` – closes the browser session.

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
