# Voice Agent - Deployment Guide

## Option 1: DigitalOcean App Platform (Recommended)

**Cost:** ~$5/month (basic-xxs) | **Setup time:** 5 minutes

### Steps

1. **Fork the repo**
   - Go to https://github.com/kavinprasathb/voice-agent
   - Click "Fork" to copy it to your GitHub account

2. **Create the app on DigitalOcean**
   - Go to https://cloud.digitalocean.com/apps
   - Click "Create App"
   - Select "GitHub" as source
   - Connect your GitHub account (one-time)
   - Select your forked `voice-agent` repo, branch `master`
   - DigitalOcean will auto-detect the Dockerfile

3. **Set environment variables**
   In the app settings, add these environment variables:

   | Variable | Value | Type |
   |----------|-------|------|
   | `SARVAM_API_KEYS` | Your Sarvam AI key(s), comma-separated | Secret |
   | `OPENAI_API_KEY` | Your OpenAI API key | Secret |
   | `EXOTEL_ACCOUNT_SID` | Your Exotel account SID | Plain |
   | `EXOTEL_API_KEY` | Your Exotel API key | Secret |
   | `EXOTEL_API_TOKEN` | Your Exotel API token | Secret |
   | `EXOTEL_PHONE_NUMBER` | Your Exotel phone number | Plain |
   | `EXOTEL_APP_ID` | Your Exotel voicebot app ID | Plain |
   | `WEBHOOK_URL` | Your n8n webhook endpoint | Plain |
   | `PORT` | `8080` | Plain |

4. **Deploy**
   - Click "Create Resources"
   - Wait for the build to complete (2-3 minutes)
   - DigitalOcean gives you a URL like: `https://voice-agent-xxxxx.ondigitalocean.app`

5. **Connect Exotel**
   - Go to Exotel Dashboard → Voicebot App → Settings
   - Set WebSocket URL to: `wss://voice-agent-xxxxx.ondigitalocean.app/ws`

6. **Test**
   ```bash
   curl -X POST https://voice-agent-xxxxx.ondigitalocean.app/call \
     -H "Content-Type: application/json" \
     -d '{
       "phone_number": "91XXXXXXXXXX",
       "vendor_name": "Test",
       "company_name": "Keeggi",
       "order_id": "TEST-001",
       "items": [
         {"name": "Chicken Biryani", "qty": 2, "price": 250, "variation": null}
       ]
     }'
   ```

---

## Option 2: Railway

**Cost:** ~$5/month | **Setup time:** 3 minutes

### Steps

1. Go to https://railway.app and sign up with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select `voice-agent` repo
4. Add the same environment variables listed above
5. Railway auto-generates a URL like: `https://voice-agent-production-xxxx.up.railway.app`
6. Set Exotel WebSocket URL to: `wss://voice-agent-production-xxxx.up.railway.app/ws`

---

## Option 3: Any VPS (Manual Setup)

**Cost:** $4-6/month | **Setup time:** 15-30 minutes

### Steps

1. SSH into your server
2. Install dependencies:
   ```bash
   sudo apt update && sudo apt install -y python3.11 python3-pip nginx certbot python3-certbot-nginx
   ```

3. Clone and setup:
   ```bash
   git clone https://github.com/kavinprasathb/voice-agent.git
   cd voice-agent
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your API keys
   nano .env
   ```

4. Create systemd service (`/etc/systemd/system/voice-agent.service`):
   ```ini
   [Unit]
   Description=Voice Agent
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/root/voice-agent
   ExecStart=/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8080
   Restart=always
   RestartSec=3
   EnvironmentFile=/root/voice-agent/.env

   [Install]
   WantedBy=multi-user.target
   ```

5. Start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable voice-agent
   sudo systemctl start voice-agent
   ```

6. Setup Nginx + SSL:
   ```bash
   # Point your domain to server IP first, then:
   sudo certbot --nginx -d voiceagent.yourdomain.com
   ```

   Nginx config (`/etc/nginx/sites-available/voiceagent`):
   ```nginx
   server {
       listen 443 ssl;
       server_name voiceagent.yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/voiceagent.yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/voiceagent.yourdomain.com/privkey.pem;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_read_timeout 300s;
       }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/voiceagent /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl restart nginx
   ```

7. Set Exotel WebSocket URL to: `wss://voiceagent.yourdomain.com/ws`

---

## Verify Deployment

After deploying on any platform, check the health endpoint:
```bash
curl https://your-app-url/
```

Expected response:
```json
{"status": "ok", "active_calls": 0, "key_pool": {"total_keys": 3, "available": 3, "in_use": 0, "waiting": 0}}
```

## API Keys Required

| Service | Sign up | What you need |
|---------|---------|---------------|
| Sarvam AI | https://www.sarvam.ai | API key for Tamil STT + TTS |
| OpenAI | https://platform.openai.com | API key for GPT-4o-mini LLM |
| Exotel | https://exotel.com | Account SID, API key, API token, phone number, app ID |
