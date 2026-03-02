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
   - This is needed because Exotel requires a secure (HTTPS) connection

3. **SSH access** to the server (you'll run commands on it remotely)
   - Your hosting provider will give you login credentials

4. **The API keys** (these go in a config file):
   - Sarvam AI key (for speech-to-text and text-to-speech)
   - OpenAI key (for the AI brain)
   - Exotel credentials (for making phone calls)
   - Webhook URL (where results are sent)

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

```bash
# Create the config file from the template
cp .env.example .env

# Open it for editing
nano .env
```

You'll see something like this. Replace the placeholder values with your real keys:

```
SARVAM_API_KEY=paste_your_sarvam_key_here
OPENAI_API_KEY=paste_your_openai_key_here
EXOTEL_ACCOUNT_SID=paste_your_exotel_sid
EXOTEL_API_KEY=paste_your_exotel_api_key
EXOTEL_API_TOKEN=paste_your_exotel_token
EXOTEL_PHONE_NUMBER=your_exotel_number
EXOTEL_APP_ID=your_exotel_app_id
WEBHOOK_URL=https://your-webhook-url/endpoint
```

If you have multiple Sarvam keys (for handling multiple calls at the same time), add them comma-separated:
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

Paste this entire block (replace `your-domain.com` with your actual domain):

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

Go to your **Exotel dashboard** and update the voicebot app's WebSocket URL to:

```
wss://your-domain.com/ws
```

This tells Exotel where to send call audio.

---

### Step 8: Test it

From any computer, run:

```bash
# Health check - should return {"status": "ok"}
curl https://your-domain.com/

# Make a test call
curl -X POST https://your-domain.com/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "8072293726",
    "vendor_name": "Kavin",
    "company_name": "Keeggi",
    "order_id": "ORD-TEST-001",
    "items": [
      {"name": "Chicken Biryani", "qty": 2, "price": 250, "variation": "medium"},
      {"name": "Paneer Butter Masala", "qty": 1, "price": 220}
    ]
  }'
```

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

## Troubleshooting

**"Connection refused" when testing:**
- Check if Docker is running: `docker ps`
- Check app logs: `docker logs voice-agent`

**Calls not connecting:**
- Make sure the Exotel WebSocket URL is set to `wss://your-domain.com/ws`
- Check that port 80 and 443 are open in your server's firewall

**SSL certificate issues:**
- Run `sudo certbot renew` to refresh the certificate
- Make sure your domain's DNS A record points to the correct server IP

**App crashes or restarts:**
- Check logs: `docker logs --tail 50 voice-agent`
- The `--restart always` flag means Docker will auto-restart it, but check logs to find the root cause
