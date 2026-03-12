# AI Freight Agent - Architecture & Plan

## Project Overview
An automated AI agent that scrapes DAT (freight load board), extracts load details, and sends intelligent automated messages to brokers on behalf of carrier companies.

## Core Features
1. **DAT Load Scraping**: Automatically scrape DAT site for available loads
2. **Load Data Extraction**: Parse and extract relevant load details (origin, destination, rate, equipment type, etc.)
3. **Broker Contact Discovery**: Extract broker email/contact information
4. **AI Message Generation**: Generate personalized, professional messages to brokers
5. **Automated Messaging**: Send messages via email or other channels
6. **Load Tracking**: Track which loads have been contacted, responses, etc.

## Technology Stack

### Core Technologies
- **Language**: Python 3.10+
- **Web Scraping**: 
  - Playwright attached to an Octo Browser profile (via CDP bridge)
- **AI/LLM Integration**:
  - OpenAI API (direct client)
- **Email Handling**:
  - SMTP for sending emails
  - IMAP for receiving/parsing responses
- **Database**:
  - SQLite (development) or PostgreSQL (production)
  - SQLAlchemy ORM
- **Bot Interface** (Optional):
  - python-telegram-bot or similar
- **Task Scheduling**:
  - APScheduler or Celery
- **Configuration**:
  - python-dotenv for environment variables
  - YAML/JSON config files

## Architecture Layers

### 1. Data Layer
- **Database Models**: Loads, Brokers, Messages, Responses
- **Repository Pattern**: Data access abstraction

### 2. Scraping Layer
- **DAT Scraper**: Main scraping engine
- **Load Parser**: Extract structured data from scraped content
- **Rate Limiting**: Respect DAT's rate limits and ToS

### 3. AI Layer
- **Message Generator**: AI-powered message creation
- **Load Analyzer**: Analyze load details for relevance
- **Response Parser**: Parse broker responses

### 4. Communication Layer
- **Email Service**: Send/receive emails
- **Message Queue**: Queue messages for sending
- **Template Engine**: Message templates

### 5. Orchestration Layer
- **Scheduler**: Schedule scraping and messaging tasks
- **Workflow Manager**: Coordinate scraping → analysis → messaging
- **Bot Interface**: User interaction (if Telegram bot)

### 6. Configuration & Logging
- **Config Manager**: Centralized configuration
- **Logging**: Comprehensive logging system
- **Error Handling**: Robust error handling and retries

## Project Structure

```
AIFreightAgent/
├── src/
│   ├── __init__.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── dat_scraper.py
│   │   ├── load_parser.py
│   │   └── rate_limiter.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── message_generator.py
│   │   ├── load_analyzer.py
│   │   └── llm_client.py
│   ├── communication/
│   │   ├── __init__.py
│   │   ├── email_service.py
│   │   ├── message_queue.py
│   │   └── templates.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── database.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── task_scheduler.py
│   ├── bot/
│   │   ├── __init__.py
│   │   └── telegram_bot.py (optional)
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       └── logger.py
├── config/
│   ├── config.yaml
│   └── .env.example
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_ai.py
│   └── test_communication.py
├── requirements.txt
├── .env
├── .gitignore
├── README.md
└── main.py
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Project setup and structure
- [ ] Database models and schema
- [ ] Configuration management
- [ ] Logging setup
- [ ] Basic DAT scraper (proof of concept)

### Phase 2: Core Scraping (Week 2)
- [ ] Full DAT scraper implementation
- [ ] Load data extraction and parsing
- [ ] Broker contact extraction
- [ ] Rate limiting and error handling
- [ ] Data persistence

### Phase 3: AI Integration (Week 3)
- [ ] LLM client setup
- [ ] Message generation logic
- [ ] Load analysis and filtering
- [ ] Template system
- [ ] Personalization engine

### Phase 4: Communication (Week 4)
- [ ] Email service implementation
- [ ] Message queue system
- [ ] Response parsing
- [ ] Delivery tracking

### Phase 5: Orchestration (Week 5)
- [ ] Task scheduler
- [ ] Workflow manager
- [ ] Bot interface (if needed)
- [ ] Monitoring and alerts

### Phase 6: Testing & Refinement (Week 6)
- [ ] Unit tests
- [ ] Integration tests
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Documentation

## Key Considerations

### Legal & Ethical
- **Terms of Service**: Ensure compliance with DAT's ToS
- **Rate Limiting**: Respect website rate limits
- **Email Compliance**: Follow CAN-SPAM and email best practices
- **Data Privacy**: Handle broker data responsibly

### Technical
- **Scalability**: Design for handling multiple loads/brokers
- **Reliability**: Error handling, retries, fallbacks
- **Security**: Secure API keys, credentials
- **Monitoring**: Logging, metrics, alerts

### Business Logic
- **Load Filtering**: Criteria for which loads to pursue
- [ ] Geographic preferences
- [ ] Rate thresholds
- [ ] Equipment type
- [ ] Load date windows
- **Message Personalization**: Customize messages based on load/broker
- **Response Handling**: Track and respond to broker replies

## Configuration Requirements

### Environment Variables
- DAT credentials (if required)
- Email SMTP settings
- LLM API keys
- Database connection
- Telegram bot token (if using)
- Rate limiting settings

### Config File Settings
- Scraping intervals
- Message templates
- Load filtering criteria
- AI model parameters
- Email templates

## Next Steps
1. Set up project structure
2. Create requirements.txt with dependencies
3. Implement database models
4. Build basic DAT scraper
5. Integrate AI message generation
6. Add email functionality
7. Create scheduler
8. Add monitoring and logging
