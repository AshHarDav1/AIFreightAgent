# Testing Guide - AI Freight Agent

## Quick Test Flow

### 1. Set Up Environment Variables

Create a `.env` file with at least:

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

# Database (default SQLite)
DATABASE_URL=sqlite:///./freight_agent.db
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Test the Flow

#### Option A: Automated Test Script

```bash
python test_flow.py
```

This will:
- Create test loads in the database
- Generate AI messages for loads
- Test email service (won't actually send if not configured)

#### Option B: Manual Testing with Telegram Bot

1. **Start the application:**
   ```bash
   python main.py
   ```

2. **Open Telegram and find your bot** (using the bot token)

3. **Test commands:**
   ```
   /start                    # Start the bot
   /test_scrape             # Create 5 test loads
   /loads                   # List all loads
   /status                  # Check system status
   /stats                   # View statistics
   /generate_message DAT123456  # Generate AI message for a load
   /send_message DAT123456     # Send message to broker (requires email config)
   ```

### 4. Test Flow Breakdown

#### Step 1: Create Test Data
```
/test_scrape
```
- Creates 5 random test loads with:
  - Random origin/destination cities
  - Random rates and miles
  - Broker contact information
  - Equipment types

#### Step 2: View Loads
```
/loads
```
- Shows recent loads from database
- Displays status, origin, destination, rate, miles

#### Step 3: Generate AI Message
```
/generate_message <load_id>
```
- Uses OpenAI API to generate personalized message
- Falls back to template if API not configured
- Shows the generated message

#### Step 4: Send Message
```
/send_message <load_id>
```
- Generates message (if not already generated)
- Sends email to broker
- Updates load status to "contacted"
- Creates message record in database

## Expected Output

### Test Script Output
```
============================================================
Testing Complete Flow
============================================================
✓ Database initialized

[Step 1] Creating test loads...
✓ Created 3 test loads

[Step 2] Listing loads...
  - Load DAT123456: Los Angeles, CA → New York, NY ($2450.50, 2789 miles)
  - Load DAT789012: Chicago, IL → Houston, TX ($1890.25, 1087 miles)
  ...

[Step 3] Generating AI message...
✓ Generated message for load DAT123456

Generated Message Preview:
------------------------------------------------------------
Hello ABC Logistics,

I represent Your Carrier Company, a reliable carrier with 10 years of experience.

I'm interested in the load from Los Angeles, CA to New York, NY (2789 miles).

We have Dry Van available and can accommodate your timeline.

Please let me know if this load is still available...
------------------------------------------------------------

[Step 4] Testing email service...
⚠ Email credentials not configured. Skipping email test.
```

### Telegram Bot Commands Output

**/status:**
```
System Status

📊 Total Loads: 5
🆕 New Loads: 5
📧 Contacted: 0
✉️ Messages Sent: 0

🤖 Bot Status: 🟢 Running
```

**/loads:**
```
Recent Loads

🆕 Load DAT123456
📍 Los Angeles, CA → New York, NY
💰 $2450.50 | 2789 miles
📊 Status: new

🆕 Load DAT789012
📍 Chicago, IL → Houston, TX
💰 $1890.25 | 1087 miles
📊 Status: new
```

## Troubleshooting

### Bot Not Responding
- Check `TELEGRAM_BOT_TOKEN` in `.env`
- Verify token is correct
- Make sure bot is started with `/start` command

### AI Messages Not Generating
- Check `OPENAI_API_KEY` in `.env`
- Verify API key is valid and has credits
- Check logs for API errors
- System will fall back to templates if API unavailable

### Email Not Sending
- Check SMTP credentials in `.env`
- For Gmail, use App Password (not regular password)
- Verify SMTP settings are correct
- Check firewall/network settings

### Database Issues
- Ensure SQLite file permissions
- Check `DATABASE_URL` in `.env`
- Verify database tables were created

## Next Steps

After testing:
1. Configure real DAT scraper (replace test data)
2. Set up production email service
3. Configure load filtering criteria
4. Set up automated scheduling
5. Monitor and optimize message response rates
