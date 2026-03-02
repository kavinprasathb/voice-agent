# How to Host the Voice Agent on Your Own Server

This guide explains how to set up the voice agent on any Linux server (like a VPS from DigitalOcean, AWS, Hostinger, etc.). No Google Cloud needed.

---

## What You Need Before Starting

1. **A Linux server** (Ubuntu is easiest) with at least 1 GB RAM
   - You can rent one from DigitalOcean, AWS, Hetzner, Hostinger, etc.
   - Cost: typically $5-10/month

2. **A domain name** pointing to your server's IP address
   - Example: `voiceagent.yourcompany.com`
   - You set this up in your domain's DNS settings — add an **A record** pointing to the server's IP
   - This is needed because Exotel requires a secure (HTTPS) connection to send call audio

3. **SSH access** to the server (you'll run commands on it remotely)
   - Your hosting provider will give you login credentials

4. **The API keys** (these go in a config file):
   - Sarvam AI key — sign up at [sarvam.ai](https://www.sarvam.ai/) (for speech-to-text and text-to-speech)
   - OpenAI key — sign up at [platform.openai.com](https://platform.openai.com/) (for the AI brain)
   - Exotel credentials — from your [Exotel dashboard](https://my.exotel.com/) (for making phone calls)
   - Webhook URL — your backend endpoint where call results will be sent

---

## Step-by-Step Setup

### Step 1: Log into your server

From your computer, open a terminal (Command Prompt / PowerShell on Windows, Terminal on Mac) and connect:

```
ssh root@your-server-ip
```

It will ask for your password. Type it and press Enter.

---

### Step 2: Install Docker

Docker is like a container that runs the app with everything it needs, so you don't have to install Python or other stuff manually.

Copy and paste these commands one by one:

```bash
# Update the server
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io

# Make Docker start automatically when server reboots
sudo systemctl enable docker
sudo systemctl start docker
```

---

### Step 3: Download the voice agent code

```bash
# Download the code from GitHub
git clone https://github.com/kavinprasathb/voice-agent.git

# Go into the folder
cd voice-agent
```

---

### Step 4: Set up your API keys

This is the main configuration step. You need to create a `.env` file with your credentials.

```bash
# Create the config file from the template
cp .env.example .env

# Open it for editing
nano .env
```

You'll see the file below. Replace each placeholder with your real value:

```
SARVAM_API_KEY=paste_your_sarvam_key_here
OPENAI_API_KEY=paste_your_openai_key_here
EXOTEL_ACCOUNT_SID=paste_your_exotel_sid
EXOTEL_API_KEY=paste_your_exotel_api_key
EXOTEL_API_TOKEN=paste_your_exotel_token
EXOTEL_PHONE_NUMBER=your_exotel_phone_number
EXOTEL_APP_ID=your_exotel_app_id
WEBHOOK_URL=https://your-backend.com/webhook
```

**Where to find each value:**

| Key | Where to get it |
|---|---|
| `SARVAM_API_KEY` | Sarvam AI dashboard → API Keys |
| `OPENAI_API_KEY` | OpenAI platform → API Keys (starts with `sk-`) |
| `EXOTEL_ACCOUNT_SID` | Exotel dashboard → Settings → Account SID |
| `EXOTEL_API_KEY` | Exotel dashboard → Settings → API Key |
| `EXOTEL_API_TOKEN` | Exotel dashboard → Settings → API Token |
| `EXOTEL_PHONE_NUMBER` | Exotel dashboard → Phone Numbers (your virtual number) |
| `EXOTEL_APP_ID` | Exotel dashboard → App Bazaar → Your voicebot app → App ID |
| `WEBHOOK_URL` | Your own backend URL where you want to receive call results (e.g. `https://yourapp.com/api/call-result`) |

If you have multiple Sarvam keys (for handling multiple calls at the same time), use this instead:
```
SARVAM_API_KEYS=key1,key2,key3
```

After editing, press **Ctrl+O** to save, then **Ctrl+X** to exit.

---

### Step 5: Build and start the app

```bash
# Build the app (takes 1-2 minutes first time)
docker build -t voice-agent .

# Start it (runs in background, auto-restarts if it crashes)
docker run -d --name voice-agent --restart always -p 8080:8080 --env-file .env voice-agent
```

To check if it's running:
```bash
docker ps
```

You should see `voice-agent` listed with status "Up".

---

### Step 6: Set up HTTPS (secure connection)

Exotel requires a secure `wss://` connection. We use **Nginx** (a web server) and **Let's Encrypt** (free SSL certificate) for this.

```bash
# Install Nginx and Certbot
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create the Nginx config file:

```bash
sudo nano /etc/nginx/sites-available/voice-agent
```

Paste this entire block — **replace `your-domain.com` with your actual domain**:

```
server {
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Save (**Ctrl+O**, **Ctrl+X**), then activate it:

```bash
# Enable the config
sudo ln -s /etc/nginx/sites-available/voice-agent /etc/nginx/sites-enabled/

# Test for errors
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Get SSL certificate (follow the prompts, enter your email)
sudo certbot --nginx -d your-domain.com
```

Certbot will automatically renew the certificate, so you don't have to worry about it expiring.

---

### Step 7: Update Exotel settings

Go to your **Exotel dashboard** → **App Bazaar** → your voicebot app → **Settings**.

Update the WebSocket URL to:

```
wss://your-domain.com/ws
```

This tells Exotel where to send call audio when a call connects.

---

### Step 8: Test it

From any computer, run:

```bash
# Health check - should return {"status": "ok"}
curl https://your-domain.com/
```

If that works, make a test call:

```bash
curl -X POST https://your-domain.com/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9876543210",
    "vendor_name": "Test Vendor",
    "company_name": "Your Company",
    "order_id": "ORD-TEST-001",
    "items": [
      {"name": "Chicken Biryani", "qty": 2, "price": 250, "variation": "medium"},
      {"name": "Paneer Butter Masala", "qty": 1, "price": 220}
    ]
  }'
```

**Replace `9876543210` with the actual phone number you want to call.**

You should get a response like:
```json
{
  "status": "ok",
  "message": "Call initiated to 9876543210",
  "call_sid": "some-unique-id",
  "order_id": "ORD-TEST-001"
}
```

---

## API Reference

### Trigger a Call

```
POST https://your-domain.com/call
Content-Type: application/json
```

**Request body:**

```json
{
  "phone_number": "9876543210",
  "vendor_name": "Vendor Name",
  "company_name": "Your Company",
  "order_id": "ORD-001",
  "items": [
    {
      "name": "Item Name",
      "qty": 2,
      "price": 250,
      "variation": "medium"
    }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `phone_number` | Yes | Vendor's phone number (10 digits) |
| `vendor_name` | Yes | Vendor's name (agent will address them by this name) |
| `company_name` | Yes | Your company name (agent says "I'm calling from [company]") |
| `order_id` | Yes | Your order reference ID |
| `items` | Yes | List of order items |
| `items[].name` | Yes | Item name |
| `items[].qty` | Yes | Quantity |
| `items[].price` | Yes | Price per unit (used for total calculation in webhook, not spoken to vendor) |
| `items[].variation` | No | Size variation: `"small"`, `"medium"`, or `"large"`. Skip or set `null` if not applicable |

### Webhook Response

When the call ends, the agent sends a **POST request** to your `WEBHOOK_URL` with:

```json
{
  "order_id": "ORD-001",
  "vendor_name": "Vendor Name",
  "company": "Your Company",
  "total_amount": 720,
  "status": "ACCEPTED",
  "call_sid": "unique-call-id",
  "rejection_reason": "reason text"
}
```

| Field | Description |
|---|---|
| `status` | One of: `ACCEPTED`, `REJECTED`, `MODIFIED`, `CALLBACK_REQUESTED`, `NO_RESPONSE`, `UNCLEAR_RESPONSE` |
| `rejection_reason` | Only present when status is `REJECTED` — contains the vendor's reason in Tamil |
| `total_amount` | Total order value (price x qty for all items) |

**What each status means:**

| Status | Meaning | What to do |
|---|---|---|
| `ACCEPTED` | Vendor confirmed the order | Process the order |
| `REJECTED` | Vendor rejected the order | Check `rejection_reason`, notify your team |
| `MODIFIED` | Vendor wants to change something in the order | Contact vendor manually to get the changes |
| `CALLBACK_REQUESTED` | Vendor asked to be called back later | Schedule a retry call |
| `NO_RESPONSE` | Vendor didn't pick up or stayed silent | Schedule a retry call |
| `UNCLEAR_RESPONSE` | Couldn't understand vendor after multiple tries | Contact vendor manually |

---

## Useful Commands (for later)

| What you want to do | Command |
|---|---|
| Check if app is running | `docker ps` |
| See live logs | `docker logs -f voice-agent` |
| Stop the app | `docker stop voice-agent` |
| Start it again | `docker start voice-agent` |
| Restart after code changes | `docker stop voice-agent && docker rm voice-agent && docker build -t voice-agent . && docker run -d --name voice-agent --restart always -p 8080:8080 --env-file .env voice-agent` |
| Edit API keys | `nano .env` (then restart the app) |
| Check server disk space | `df -h` |
| Check server memory | `free -h` |

---

## Updating the App (when new code is available)

```bash
cd voice-agent

# Pull latest code
git pull

# Rebuild and restart
docker stop voice-agent
docker rm voice-agent
docker build -t voice-agent .
docker run -d --name voice-agent --restart always -p 8080:8080 --env-file .env voice-agent
```

---

## Customization

If you want to change any of the following, edit the file mentioned and rebuild:

| What to change | File to edit | What to look for |
|---|---|---|
| Agent's name (currently "Ramesh") | `config.py` | Search for `Ramesh` in `build_system_prompt()` |
| Company name in greeting | Sent via API | Change `company_name` in your `/call` request |
| Language (currently Tamil only) | `config.py` | Change `LANGUAGE`, STT/TTS settings, and rewrite the system prompt |
| AI model (currently GPT-4o-mini) | `config.py` | Change `OPENAI_LLM_MODEL` |
| Silence timeout (currently 7 seconds) | `agent.py` | Change `self._silence_timeout_sec = 7` |
| Max retry prompts before hanging up | `agent.py` | Change `self._max_silence_prompts = 2` |
| TTS voice/speed | `config.py` | Change `SPEAKER` and `TTS_PACE` |

After any file change, rebuild and restart (see "Updating the App" above).

---

## Troubleshooting

**"Connection refused" when testing:**
- Check if Docker is running: `docker ps`
- Check app logs: `docker logs voice-agent`

**Calls not connecting:**
- Make sure the Exotel WebSocket URL is set to `wss://your-domain.com/ws`
- Check that port 80 and 443 are open in your server's firewall
- Check Exotel dashboard for call logs

**Webhook not receiving data:**
- Check that `WEBHOOK_URL` in `.env` is correct and publicly reachable
- Check app logs: `docker logs -f voice-agent` — look for "Sending webhook" lines

**Agent not speaking or speaking gibberish:**
- Check Sarvam API key is valid and has credits
- Check logs for TTS errors: `docker logs voice-agent | grep TTS`

**Agent not understanding vendor:**
- Check Sarvam API key for STT
- Check logs for STT errors: `docker logs voice-agent | grep STT`

**SSL certificate issues:**
- Run `sudo certbot renew` to refresh the certificate
- Make sure your domain's DNS A record points to the correct server IP

**App crashes or restarts:**
- Check logs: `docker logs --tail 50 voice-agent`
- The `--restart always` flag means Docker will auto-restart it, but check logs to find the root cause

---

## Approximate Costs Per Call

| Service | Cost per call (approx) |
|---|---|
| Exotel (telephony) | Depends on your Exotel plan |
| Sarvam AI (STT + TTS) | ~₹1-2 |
| OpenAI GPT-4o-mini (LLM) | ~₹0.5-1 |
| Server | ~$5-10/month flat (unlimited calls) |
