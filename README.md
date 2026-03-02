# AI Freight Agent

An automated AI agent that scrapes DAT (freight load board), extracts load details, and sends intelligent automated messages to brokers on behalf of carrier companies.

## Features

- 🔍 **Automated Load Scraping**: Scrapes DAT site for available freight loads
- 📊 **Smart Load Analysis**: AI-powered analysis of load details
- ✉️ **Automated Messaging**: Sends personalized messages to brokers
- 📧 **Email Integration**: Handles email communication with brokers
- 🤖 **AI-Powered**: Uses LLM to generate professional, personalized messages
- 📈 **Tracking**: Tracks loads, messages, and broker responses

## Project Status

🚧 **In Development** - Currently in planning and initial setup phase

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture and implementation plan.

## Setup

### Prerequisites
- Python 3.10+
- pip
- (Optional) PostgreSQL for production

### Installation

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```
5. Update `.env` with your credentials:
   - DAT credentials (if required)
   - Email SMTP settings
   - LLM API keys (OpenAI, Anthropic, etc.)
   - Database connection

## Quick Start

### 1. Set Up Environment

Create a `.env` file in the project root:

```bash
# Required for Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Required for AI Message Generation
OPENAI_API_KEY=sk-your_openai_api_key

# Optional - for email sending
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Application

```bash
python main.py
```

### 4. Test the Flow

**Option A: Automated Test**
```bash
python test_flow.py
```

**Option B: Telegram Bot Commands**
- Open Telegram and find your bot
- Use commands: `/start`, `/test_scrape`, `/loads`, `/generate_message <load_id>`, `/send_message <load_id>`

See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for detailed testing instructions.

## Usage

```bash
python main.py
```

## Configuration

See `config/config.yaml` and `.env` for configuration options.

## Development

### Project Structure
- `src/` - Main source code
- `config/` - Configuration files
- `tests/` - Test files
- `main.py` - Entry point

### Running Tests
```bash
pytest tests/
```

## Legal & Ethical Considerations

⚠️ **Important**: 
- Ensure compliance with DAT's Terms of Service
- Respect rate limits and website policies
- Follow email compliance regulations (CAN-SPAM)
- Handle broker data responsibly

## License

[To be determined]

## Contributing

[To be determined]
