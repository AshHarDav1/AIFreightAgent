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

## Octo Bridge (when app runs in Docker)

If the app runs in Docker but Octo Browser runs on the host (bound to `127.0.0.1:58888`), the container cannot reach it directly. Run a small TCP bridge **on the host**:

1. **Install socat** (once):
   ```bash
   # Debian/Ubuntu
   sudo apt install socat
   # macOS
   brew install socat
   ```

2. **Start the bridge** (on the Octo host, keep it running):
   ```bash
   ./scripts/octo-bridge.sh
   ```
   Or manually: `socat TCP-LISTEN:58889,fork,reuseaddr TCP:127.0.0.1:58888`

3. **In `.env`** (for the Dockerized app):
   ```env
   OCTO_LOCAL_API_URL=http://host.docker.internal:58889
   ```

4. **Firewall (secure)** — The container reaches the bridge on the host’s port (e.g. 58889). This port is listened by socat which redirects traffic through the bridge to `127.0.0.1:58888` where Octo is listening. Many hosts block this by default. **Do not** open the port to the whole internet (`ufw allow 58889/tcp`). Allow it only from the Docker network subnet so only your containers can connect:

   - Find the Docker subnet (replace `aifreightagent_default` if your project name differs):
     ```bash
     docker network ls
     docker network inspect aifreightagent_default | grep -A5 '"IPAM"'
     ```
     Or for the default bridge: `docker network inspect bridge | grep -A5 '"IPAM"'`. Note the `Subnet` (e.g. `172.18.0.0/16`).

   - Allow port 58889 only from that subnet (replace `172.18.0.0/16` with your subnet):
     ```bash
     sudo ufw allow from 172.18.0.0/16 to any port 58889 proto tcp
     sudo ufw reload
     ```
   Container IPs change on each rebuild; the subnet stays the same, so this remains valid.

Optional env vars when running the script: `BRIDGE_PORT=58889` (default), `OCTO_PORT=58888` (Octo’s port).

### Octo CDP Bridge Manager (for Docker)

Octo’s automation API returns a CDP WebSocket like `ws://127.0.0.1:PORT/devtools/browser/...` where `PORT` changes per profile start. When the app runs in Docker, it cannot connect directly to `127.0.0.1:PORT` on the host. The CDP bridge manager creates a small TCP proxy per CDP port.

1. **Run the manager** on the Octo host (Linux/Windows/macOS):

   ```bash
   python scripts/octo-cdp-bridge-manager.py
   ```

   This starts an HTTP server on `0.0.0.0:58890` and uses a bridge port range `60000–60100` for CDP tunnels.

2. **In `.env`** (for the Dockerized app):

   ```env
   OCTO_CDP_BRIDGE_URL=http://host.docker.internal:58890
   ```

3. **Firewall (secure)** — Similar to the main Octo bridge, allow access only from the Docker subnet:

   ```bash
   # Example; replace 172.18.0.0/16 with your Docker subnet
   sudo ufw allow from 172.18.0.0/16 to any port 58890 proto tcp
   sudo ufw allow from 172.18.0.0/16 to any port 60000:60100 proto tcp
   sudo ufw reload
   ```

   This allows containers on the Docker network to reach the CDP manager and its bridge ports, while keeping them closed to the rest of the world.

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
