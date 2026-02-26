# 🚀 Quick Setup Guide

Follow these steps to get your browser automation agent running!

## Step 1: Install Python Packages

Open PowerShell in the `browser-agent` folder and run:

```powershell
pip install -r requirements.txt
```

This installs:
- playwright (browser automation)
- openai (GPT-4 support)
- anthropic (Claude support)
- fastapi (REST API)
- uvicorn (web server)
- python-dotenv (environment variables)

## Step 2: Install Playwright Browsers

```powershell
playwright install chromium
```

This downloads Chromium browser (~300MB). It only needs to be done once.

## Step 3: Set Up Your API Key

### Option A: OpenAI (Recommended)

1. **Copy the example env file:**
   ```powershell
   Copy-Item .env.example .env
   ```

2. **Get your OpenAI API key:**
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Copy it

3. **Edit `.env` file:**
   ```powershell
   notepad .env
   ```
   
   Replace `sk-your-api-key-here` with your actual key:
   ```env
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
   OPENAI_MODEL=gpt-4-turbo-preview
   DEFAULT_PROVIDER=openai
   ```

### Option B: Anthropic Claude

1. Get API key from https://console.anthropic.com/
2. Edit `.env`:
   ```env
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
   DEFAULT_PROVIDER=anthropic
   ```

### Option C: Google Gemini

1. Get API key from https://aistudio.google.com/app/apikey
2. Edit `.env`:
   ```env
   GOOGLE_API_KEY=xxxxxxxxxxxxx
   GOOGLE_MODEL=gemini-2.0-flash-exp
   DEFAULT_PROVIDER=google
   ```

## Step 4: Test the Agent

Run the test script:

```powershell
python agent.py
```

You should see:
- ✓ Agent initialized
- ✓ Browser started
- Browser window opens
- Agent navigates to Google
- Agent describes what it sees
- ✓ Browser closed

## Step 5: Customize Your Task

Edit `agent.py` at the bottom to change what the agent does:

```python
# Example: Google Search
agent.run(
    "Search for 'browser automation' on Google and tell me the first result",
    initial_url="https://google.com"
)

# Example: Data Extraction
agent.run(
    "Go to Hacker News and list the top 5 story titles",
    initial_url="https://news.ycombinator.com"
)

# Example: Form Filling
agent.run(
    "Fill out the contact form with my information",
    initial_url="https://yoursite.com/contact"
)
```

## Step 6 (Optional): Google Sheets Integration

The agent can directly read, write, and create Google Spreadsheets via the Sheets API (much faster than browser-based interaction).

### One-Time Setup (Developer Only)

If `client_secret.json` is already included in the project, skip to **User Setup** below.

To create your own OAuth credentials:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Google Sheets API**:
   - Go to **APIs & Services** → **Library**
   - Search for "Google Sheets API" and click **Enable**
4. Configure the **OAuth consent screen**:
   - Go to **APIs & Services** → **OAuth consent screen**
   - Choose **External** user type
   - Fill in app name and your email
   - Add scopes: `https://www.googleapis.com/auth/spreadsheets` and `openid` and `email`
   - Add your Google account as a **test user**
5. Create **OAuth 2.0 credentials**:
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**
   - Choose **Web application**
   - Add `http://localhost:8000/auth/google/callback` as an **Authorized redirect URI**
   - Download the credentials and save as `client_secret.json` in the project root

### User Setup

1. Start the server (`python server.py`) and open the frontend
2. Go to **Settings** → **Google Account**
3. Click **Connect Google Account**
4. Sign in with your Google account and grant access
5. The window will auto-close — you're connected!

Now the agent can use `readSpreadsheet`, `writeSpreadsheet`, `createSpreadsheet`, etc. when you ask it to work with Google Sheets.

## Step 7 (Optional): Run API Server

For REST API access:

```powershell
python server.py
```

Then test with:
```powershell
# Use curl or Invoke-RestMethod
Invoke-RestMethod -Uri http://localhost:8000/task -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"instruction":"Go to google.com","initial_url":"https://google.com"}' | ConvertTo-Json
```

Or visit http://localhost:8000/docs for interactive API docs.

## ✅ Verification Checklist

- [ ] Python 3.8+ installed
- [ ] All packages installed (`pip install -r requirements.txt`)
- [ ] Playwright browsers installed (`playwright install chromium`)
- [ ] `.env` file created with API key
- [ ] Test run successful (`python agent.py`)

## 🐛 Troubleshooting

### Error: "No module named 'playwright'"
```powershell
pip install playwright
playwright install chromium
```

### Error: "API key not found"
Check that `.env` file exists and has your key:
```powershell
cat .env
```

### Error: "Could not find browser"
```powershell
playwright install chromium
```

### Browser doesn't open
Try non-headless mode in `agent.py`:
```python
agent = BrowserAgent(headless=False)  # Should see browser window
```

## 🎯 Next Steps

1. **Try example tasks** - Modify `agent.py` with different instructions
2. **Build your own automation** - Create custom workflows
3. **Use the API** - Integrate with other applications
4. **Experiment with prompts** - See how the agent handles different tasks

## 💡 Tips

- Start with simple tasks (navigate, click, read)
- Be specific in instructions
- Watch the browser to see what it's doing
- Check console output for debugging
- Use GPT-4 Turbo for best results

## 🎉 You're Ready!

Your browser automation agent is set up. Try it with:

```python
from agent import BrowserAgent

agent = BrowserAgent()
agent.start()

agent.run(
    "Your instruction here",
    initial_url="https://example.com"
)

agent.close()
```

Enjoy automating! 🚀
