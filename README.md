# Browser Automation Agent

A powerful browser automation agent powered by LLMs (OpenAI, Anthropic, Google Gemini) and Playwright. This agent can understand natural language instructions and complete complex web automation tasks.

## 🎯 Features

- **Natural Language Control**: Just describe what you want, the agent figures out how to do it
- **Multiple LLM Providers**: OpenAI (GPT-4), Anthropic (Claude), Google (Gemini)
- **Smart Element Detection**: Uses accessibility tree to find interactive elements
- **Robust Interaction**: Multiple fallback strategies for clicking and typing
- **Visual Feedback**: See the browser in action (non-headless mode)
- **REST API**: Control via HTTP endpoints
- **Tool Calling**: LLM can use 10+ browser automation tools

## 🚀 Quick Start

### 1. Install Dependencies

```powershell
# Navigate to project directory
cd browser-agent

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure API Keys

```powershell
# Copy example env file
Copy-Item .env.example .env

# Edit .env and add your API key
notepad .env
```

Add your API key:
```env
# For OpenAI (recommended)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview
DEFAULT_PROVIDER=openai

# OR for Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-your-api-key-here
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# DEFAULT_PROVIDER=anthropic
```

### 3. Run the Agent

**Option A: Direct Python Script**

```powershell
python agent.py
```

Edit `agent.py` to customize the task:
```python
agent.run(
    "Search for 'playwright' on Google and click the first result",
    initial_url="https://google.com"
)
```

**Option B: REST API Server**

```powershell
python server.py
```

Then use the API:
```powershell
# Start browser
curl -X POST http://localhost:8000/start

# Run task
curl -X POST http://localhost:8000/task -H "Content-Type: application/json" -d '{
  "instruction": "Go to google.com and search for playwright",
  "initial_url": "https://google.com"
}'

# Stop browser
curl -X POST http://localhost:8000/stop
```

## 📖 Usage Examples

### Example 1: Web Search

```python
from agent import BrowserAgent

agent = BrowserAgent()
agent.start()

agent.run(
    "Search for 'browser automation' on Google and summarize the first 3 results",
    initial_url="https://google.com"
)

agent.close()
```

### Example 2: Form Filling

```python
agent.run(
    "Fill out the contact form with name 'John Doe' and email 'john@example.com', then submit",
    initial_url="https://example.com/contact"
)
```

### Example 3: Data Extraction

```python
agent.run(
    "Go to Hacker News and list the top 5 article titles",
    initial_url="https://news.ycombinator.com"
)
```

### Example 4: E-commerce

```python
agent.run(
    "Search for 'laptop' on Amazon, filter by 4+ stars, and tell me the price of the first result",
    initial_url="https://amazon.com"
)
```

## 🛠️ Available Tools

The agent has access to these browser automation tools:

1. **getInteractiveSnapshot()** - Get all clickable/typeable elements on page
2. **click(nodeId)** - Click an element
3. **inputText(nodeId, text)** - Type into input fields
4. **navigate(url)** - Go to a URL
5. **scrollDown()** / **scrollUp()** - Scroll the page
6. **getPageContent()** - Extract text content
7. **captureScreenshot()** - Take a screenshot
8. **sendKeys(key)** - Send special keys (Enter, Tab, etc.)
9. **getPageLoadStatus()** - Check if page loaded

## 🔧 Configuration

### Environment Variables

```env
# LLM Provider
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
DEFAULT_PROVIDER=openai

# Server Settings
HOST=127.0.0.1
PORT=8000
```

### Provider Comparison

| Provider | Model | Speed | Cost | Best For |
|----------|-------|-------|------|----------|
| OpenAI | GPT-4 Turbo | Fast | $$$ | Complex tasks |
| Anthropic | Claude 3.5 Sonnet | Fast | $$$ | Long context |
| Google | Gemini 2.0 Flash | Very Fast | $ | Simple tasks |

## 📡 REST API

### Endpoints

**POST /start** - Start browser agent
```json
{
  "provider": "openai",
  "headless": false
}
```

**POST /task** - Run automation task
```json
{
  "instruction": "Search for 'AI' on Google",
  "initial_url": "https://google.com",
  "provider": "openai"
}
```

**POST /stop** - Stop browser agent

**GET /status** - Get agent status

**GET /** - API documentation

### Interactive API Docs

Visit http://localhost:8000/docs for Swagger UI

## 🎓 How It Works

### Architecture

```
User Instruction
      ↓
LLM (GPT-4/Claude)
      ↓
Tool Calls (function calling)
      ↓
Browser Controller (Playwright)
      ↓
Chromium Browser
```

### Workflow

1. **User gives instruction** (e.g., "Search for X on Google")
2. **LLM analyzes task** and decides which tools to use
3. **Agent executes tools**:
   - `getInteractiveSnapshot()` → sees search box
   - `click(nodeId: 5)` → clicks search box
   - `inputText(nodeId: 5, text: "X")` → types query
   - `sendKeys("Enter")` → submits search
4. **LLM verifies** results and continues or finishes
5. **Agent returns** final result to user

### Smart Element Detection

Uses Playwright's accessibility tree to find elements:
- **Semantic Understanding**: Knows a button is a button, not just a div
- **Multiple Strategies**: Tries role, text, label, coordinates
- **Robust**: Works even when DOM changes

## 🐛 Troubleshooting

### "No module named 'playwright'"
```powershell
pip install playwright
playwright install chromium
```

### "API key not found"
Make sure `.env` file exists and contains your API key:
```powershell
notepad .env
```

### "Element not found"
The agent will try multiple strategies. If it fails:
- Try scrolling to element first
- Use `getInteractiveSnapshot()` to see available elements
- Check if page is fully loaded with `getPageLoadStatus()`

### Browser doesn't open
Make sure Playwright browsers are installed:
```powershell
playwright install chromium
```

## 🎯 Advanced Usage

### Custom System Prompt

Modify `llm_client.py` → `get_system_prompt()` to customize agent behavior

### Add New Tools

1. Add method to `browser_controller.py`
2. Add tool definition to `llm_client.py` → `get_tools_definition()`
3. Add execution case in `agent.py` → `execute_tool()`

### Change Browser Settings

Edit `browser_controller.py` → `start()`:
```python
self.browser = self.playwright.chromium.launch(
    headless=True,  # Run in background
    args=['--start-maximized', '--disable-blink-features=AutomationControlled']
)
```

## 📊 Performance Tips

1. **Use GPT-4 Turbo** for best results (faster than GPT-4)
2. **Limit iterations** to avoid costs: `agent.max_iterations = 10`
3. **Use viewport_only=True** in getInteractiveSnapshot for speed
4. **Be specific** in instructions to reduce LLM iterations
5. **Chain simple tasks** instead of complex multi-step ones

## 🔐 Security

- API keys stored in `.env` (never commit!)
- Browser runs locally (no cloud automation)
- CORS enabled (restrict in production)
- No data sent to BrowserOS servers

## 📝 License

MIT License - Feel free to use and modify!

## 🤝 Contributing

This is a learning project. Feel free to:
- Add new tools
- Support more LLM providers
- Improve element detection
- Add better error handling

## 🆘 Support

Issues? Questions?
1. Check this README
2. Review example code in `agent.py`
3. Check API docs at http://localhost:8000/docs
4. Review browser console output

## 🎉 What's Next?

- Add support for file uploads
- Implement session management
- Add screenshot comparison
- Support multi-tab automation
- Add proxy support
- Implement CAPTCHA handling
