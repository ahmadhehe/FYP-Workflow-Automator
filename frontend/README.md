# Browser Agent Dashboard

A professional React dashboard for the Browser Automation Agent.

## Features

- **Real-time Task Monitoring**: Watch agent actions in real-time via WebSocket
- **Flow History**: View, edit, and re-run previous automation flows
- **Beautiful UI**: Modern dark theme with Tailwind CSS
- **Provider Selection**: Choose between OpenAI and Anthropic

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend server running on http://localhost:8000

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm start
```

The app will be available at http://localhost:3000

### Production Build

```bash
npm run build
```

## Configuration

Create a `.env` file in the frontend directory:

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws
```

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── ActionTimeline.jsx  # Real-time action feed
│   │   ├── Dashboard.jsx       # Main dashboard view
│   │   ├── FlowHistory.jsx     # Flow history & management
│   │   ├── ResultPanel.jsx     # Task result display
│   │   ├── Settings.jsx        # App settings
│   │   ├── Sidebar.jsx         # Navigation sidebar
│   │   ├── StatusBar.jsx       # Status indicators
│   │   └── TaskInput.jsx       # Task input form
│   ├── hooks/
│   │   └── useWebSocket.js     # WebSocket connection hook
│   ├── services/
│   │   └── api.js              # API service layer
│   ├── App.jsx
│   ├── index.css
│   └── index.js
├── package.json
└── tailwind.config.js
```
