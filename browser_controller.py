"""
Browser Controller - Handles all browser automation using Playwright
"""
from playwright.sync_api import sync_playwright, Page, Browser, Playwright, BrowserContext
from typing import Dict, List, Any, Optional
import base64
import time
import os
import logging

logger = logging.getLogger(__name__)

# Default profile directory for persistent browser data
DEFAULT_PROFILE_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")


# ── Overlay injection ────────────────────────────────────────────────────────
# Self-contained JS injected into every page + new tab via context.add_init_script.
# Uses Shadow DOM so page CSS can't affect it and it can't affect page layout.
# Host is pointer-events:none; interactive bits inside the shadow re-enable
# pointer-events so automation (coordinate-based CDP clicks) never hits the panel.
OVERLAY_SCRIPT = r"""
(() => {
  if (window.__agentOverlayInjected) return;
  window.__agentOverlayInjected = true;

  // Don't inject into iframes — only the top document gets the overlay.
  if (window.top !== window.self) return;

  // Defer until <body> exists — init scripts can run before DOM is ready.
  const install = () => {
    if (!document.body) {
      requestAnimationFrame(install);
      return;
    }

    const BACKEND_HTTP = 'http://localhost:8000';
    const BACKEND_WS   = 'ws://localhost:8000/ws';

    // Host container (page-visible, but pointer-events none so it doesn't block clicks)
    const host = document.createElement('div');
    host.id = '__agent_overlay_host__';
    host.style.cssText = [
      'position:fixed', 'inset:0',
      'pointer-events:none',
      'z-index:2147483647',
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
    ].join(';');
    document.documentElement.appendChild(host);
    const root = host.attachShadow({ mode: 'open' });

    const style = document.createElement('style');
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .panel, .modal-backdrop, .btn, input, .header, .minimized-btn {
        pointer-events: auto;
      }
      .panel {
        position: absolute;
        bottom: 20px;
        right: 20px;
        width: 340px;
        background: rgba(255, 255, 255, 0.72);
        backdrop-filter: blur(18px) saturate(180%);
        -webkit-backdrop-filter: blur(18px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.6);
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.06);
        color: #1a1a1a;
        overflow: hidden;
        transition: opacity 180ms ease, transform 180ms ease;
        font-size: 13px;
      }
      .panel.hidden { opacity: 0; transform: translateY(12px); pointer-events: none; }
      .header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 10px 14px;
        cursor: grab;
        border-bottom: 1px solid rgba(0, 0, 0, 0.06);
        background: linear-gradient(180deg, rgba(255,255,255,0.4), rgba(255,255,255,0));
      }
      .header.dragging { cursor: grabbing; }
      .title { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; }
      .status-dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: #3b82f6;
        box-shadow: 0 0 8px rgba(59, 130, 246, 0.7);
        animation: pulse 1.6s ease-in-out infinite;
      }
      .status-dot.complete { background: #10b981; box-shadow: 0 0 8px rgba(16,185,129,0.7); animation: none; }
      .status-dot.intervention { background: #f59e0b; box-shadow: 0 0 8px rgba(245,158,11,0.7); }
      .status-dot.error { background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,0.7); animation: none; }
      .status-dot.idle { background: #9ca3af; box-shadow: none; animation: none; }
      @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.55; transform: scale(0.88); }
      }
      .header-controls { display: flex; gap: 4px; }
      .icon-btn {
        width: 22px; height: 22px; border: 0; background: transparent;
        border-radius: 6px; cursor: pointer; color: #555;
        display: flex; align-items: center; justify-content: center;
        font-size: 14px; line-height: 1;
        transition: background 120ms;
      }
      .icon-btn:hover { background: rgba(0, 0, 0, 0.06); }
      .body { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
      .task {
        font-size: 12px; line-height: 1.4; color: #444;
        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
        overflow: hidden;
        max-height: 3.8em;
      }
      .progress-row { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #666; }
      .progress-track {
        flex: 1; height: 4px; background: rgba(0, 0, 0, 0.08);
        border-radius: 2px; overflow: hidden;
      }
      .progress-fill {
        height: 100%; background: linear-gradient(90deg, #8b1a1a, #c39340);
        width: 0%; transition: width 300ms ease;
      }
      .action-text {
        font-size: 11px; color: #555;
        padding: 6px 8px; background: rgba(0,0,0,0.04); border-radius: 6px;
        max-height: 2.4em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .btn {
        border: 0; border-radius: 8px; padding: 8px 12px;
        font-size: 12px; font-weight: 600; cursor: pointer;
        transition: transform 90ms, box-shadow 120ms, background 120ms;
      }
      .btn:active { transform: translateY(1px); }
      .btn-danger { background: rgba(239, 68, 68, 0.95); color: #fff; }
      .btn-danger:hover { background: rgba(220, 38, 38, 1); }
      .btn-secondary { background: rgba(0,0,0,0.08); color: #222; }
      .btn-secondary:hover { background: rgba(0,0,0,0.14); }
      .btn-primary {
        background: linear-gradient(180deg, #8b1a1a, #6b1010); color: #fff;
        box-shadow: 0 4px 12px rgba(139, 26, 26, 0.35);
      }
      .btn-primary:hover { filter: brightness(1.08); }
      .btn-row { display: flex; gap: 6px; }
      .confirm-card {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 8px 10px; border-radius: 8px;
        font-size: 12px;
      }
      .confirm-card .label { margin-bottom: 6px; color: #991b1b; }

      .minimized-btn {
        position: absolute; bottom: 20px; right: 20px;
        width: 48px; height: 48px; border-radius: 50%;
        background: rgba(255,255,255,0.75);
        backdrop-filter: blur(18px) saturate(180%);
        -webkit-backdrop-filter: blur(18px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.6);
        box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        display: flex; align-items: center; justify-content: center;
        cursor: pointer;
        font-size: 18px;
        transition: transform 120ms;
      }
      .minimized-btn.hidden { display: none; }
      .minimized-btn:hover { transform: scale(1.06); }

      .modal-backdrop {
        position: absolute; inset: 0;
        background: rgba(15, 15, 20, 0.55);
        backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
        display: none; align-items: center; justify-content: center;
        animation: fadeIn 180ms ease;
      }
      .modal-backdrop.active { display: flex; }
      @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      @keyframes springIn {
        0%   { opacity: 0; transform: scale(0.85) translateY(16px); }
        60%  { opacity: 1; transform: scale(1.02) translateY(-2px); }
        100% { opacity: 1; transform: scale(1)    translateY(0); }
      }
      .modal {
        width: min(440px, 90vw);
        background: rgba(255,255,255,0.92);
        backdrop-filter: blur(24px) saturate(180%);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        border-radius: 18px;
        padding: 22px 22px 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.35);
        animation: springIn 320ms cubic-bezier(0.34, 1.56, 0.64, 1);
        color: #1a1a1a;
      }
      .modal .icon {
        width: 56px; height: 56px; border-radius: 14px;
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        display: flex; align-items: center; justify-content: center;
        font-size: 28px; margin-bottom: 14px;
      }
      .modal h2 { font-size: 16px; margin: 0 0 6px; font-weight: 700; }
      .modal p  { font-size: 13px; line-height: 1.5; color: #444; margin: 0 0 14px; }
      .modal input {
        width: 100%; padding: 10px 12px;
        border: 1px solid rgba(0,0,0,0.14);
        border-radius: 10px;
        font-size: 14px;
        background: rgba(255,255,255,0.9);
        margin-bottom: 14px;
        outline: none;
        transition: border-color 120ms, box-shadow 120ms;
      }
      .modal input:focus {
        border-color: #8b1a1a;
        box-shadow: 0 0 0 3px rgba(139, 26, 26, 0.15);
      }
      .modal .actions { display: flex; gap: 8px; justify-content: flex-end; }
    `;
    root.appendChild(style);

    // Panel HTML
    const wrap = document.createElement('div');
    wrap.innerHTML = `
      <div class="panel" id="panel">
        <div class="header" id="header">
          <div class="title">
            <span class="status-dot idle" id="statusDot"></span>
            <span id="statusLabel">Agent</span>
          </div>
          <div class="header-controls">
            <button class="icon-btn" id="minBtn" title="Minimize">—</button>
          </div>
        </div>
        <div class="body">
          <div class="task" id="task">Waiting for task…</div>
          <div class="progress-row">
            <span id="iterText">0 / 0</span>
            <div class="progress-track"><div class="progress-fill" id="progressFill"></div></div>
          </div>
          <div class="action-text" id="actionText">Idle</div>
          <div id="stopRegion">
            <button class="btn btn-danger" id="stopBtn" style="width:100%">Stop</button>
          </div>
        </div>
      </div>

      <div class="minimized-btn hidden" id="minimized" title="Show agent panel">⚡</div>

      <div class="modal-backdrop" id="modalBackdrop">
        <div class="modal">
          <div class="icon" id="modalIcon">👆</div>
          <h2 id="modalTitle">Action Required</h2>
          <p id="modalMessage">Please complete the action.</p>
          <input type="text" id="modalInput" placeholder="Enter response (optional)…" />
          <div class="actions">
            <button class="btn btn-secondary" id="modalSkip">Done (no input)</button>
            <button class="btn btn-primary" id="modalSubmit">Submit</button>
          </div>
        </div>
      </div>
    `;
    root.appendChild(wrap);

    const $ = (id) => root.getElementById(id);
    const panel       = $('panel');
    const header      = $('header');
    const statusDot   = $('statusDot');
    const statusLabel = $('statusLabel');
    const taskEl      = $('task');
    const iterText    = $('iterText');
    const progressFill= $('progressFill');
    const actionText  = $('actionText');
    const stopRegion  = $('stopRegion');
    const minBtn      = $('minBtn');
    const minimized   = $('minimized');
    const modalBackdrop = $('modalBackdrop');
    const modalIcon     = $('modalIcon');
    const modalTitle    = $('modalTitle');
    const modalMessage  = $('modalMessage');
    const modalInput    = $('modalInput');
    const modalSkip     = $('modalSkip');
    const modalSubmit   = $('modalSubmit');

    // Minimize / restore
    minBtn.addEventListener('click', () => {
      panel.classList.add('hidden');
      minimized.classList.remove('hidden');
    });
    minimized.addEventListener('click', () => {
      panel.classList.remove('hidden');
      minimized.classList.add('hidden');
    });

    // Drag
    let dragState = null;
    header.addEventListener('mousedown', (e) => {
      if (e.target.closest('.icon-btn')) return;
      const rect = panel.getBoundingClientRect();
      dragState = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
      panel.style.right = 'auto';
      panel.style.bottom = 'auto';
      panel.style.left = rect.left + 'px';
      panel.style.top  = rect.top  + 'px';
      header.classList.add('dragging');
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
      if (!dragState) return;
      const x = Math.max(8, Math.min(window.innerWidth  - panel.offsetWidth  - 8, e.clientX - dragState.dx));
      const y = Math.max(8, Math.min(window.innerHeight - panel.offsetHeight - 8, e.clientY - dragState.dy));
      panel.style.left = x + 'px';
      panel.style.top  = y + 'px';
    });
    window.addEventListener('mouseup', () => {
      if (dragState) header.classList.remove('dragging');
      dragState = null;
    });

    // Stop with inline confirmation
    const renderStop = () => {
      stopRegion.innerHTML = '';
      const btn = document.createElement('button');
      btn.className = 'btn btn-danger';
      btn.style.width = '100%';
      btn.textContent = 'Stop';
      btn.addEventListener('click', () => {
        stopRegion.innerHTML = `
          <div class="confirm-card">
            <div class="label">Stop automation?</div>
            <div class="btn-row">
              <button class="btn btn-secondary" id="stopCancel" style="flex:1">Cancel</button>
              <button class="btn btn-danger" id="stopConfirm" style="flex:1">Stop</button>
            </div>
          </div>
        `;
        root.getElementById('stopCancel').addEventListener('click', renderStop);
        root.getElementById('stopConfirm').addEventListener('click', () => {
          fetch(BACKEND_HTTP + '/stop', { method: 'POST' }).catch(() => {});
          setStatus('stopped');
          actionText.textContent = 'Stop requested…';
          renderStop();
        });
      });
      stopRegion.appendChild(btn);
    };
    renderStop();

    // Status helpers
    const STATUS_MAP = {
      running:      { cls: '',            label: 'Running' },
      initializing: { cls: '',            label: 'Starting…' },
      complete:     { cls: 'complete',    label: 'Complete' },
      completed:    { cls: 'complete',    label: 'Complete' },
      intervention: { cls: 'intervention',label: 'Needs you' },
      stopped:      { cls: 'error',       label: 'Stopped' },
      failed:       { cls: 'error',       label: 'Failed' },
      error:        { cls: 'error',       label: 'Error' },
      idle:         { cls: 'idle',        label: 'Idle' },
    };
    const setStatus = (s) => {
      const cfg = STATUS_MAP[s] || STATUS_MAP.idle;
      statusDot.className = 'status-dot ' + cfg.cls;
      statusLabel.textContent = cfg.label;
    };

    const REASON_ICONS = {
      captcha: '🤖',
      otp: '🔐',
      '2fa': '🔐',
      login: '🔑',
      cookie_consent: '🍪',
      manual: '👆',
      other: '❓',
    };

    // Intervention modal
    let currentIntervention = null;
    const openModal = (message, reason) => {
      currentIntervention = { message, reason };
      modalIcon.textContent = REASON_ICONS[reason] || '👆';
      modalTitle.textContent = reason === 'captcha' ? 'Solve CAPTCHA'
        : reason === 'otp' || reason === '2fa' ? 'Enter verification code'
        : reason === 'login' ? 'Please log in'
        : reason === 'cookie_consent' ? 'Cookie consent'
        : 'Action required';
      modalMessage.textContent = message || 'Please complete the required action.';
      modalInput.value = '';
      modalBackdrop.classList.add('active');
      setStatus('intervention');
      setTimeout(() => modalInput.focus(), 50);
    };
    const closeModal = () => {
      modalBackdrop.classList.remove('active');
      currentIntervention = null;
    };

    const submitIntervention = (response) => {
      fetch(BACKEND_HTTP + '/intervention/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response: response || '' }),
      }).catch(() => {});
      closeModal();
    };

    modalSubmit.addEventListener('click', () => submitIntervention(modalInput.value));
    modalSkip.addEventListener('click', () => submitIntervention(''));
    modalInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); submitIntervention(modalInput.value); }
      if (e.key === 'Escape') { e.preventDefault(); /* don't auto-submit on escape */ }
    });

    // Catch up on state for newly loaded pages — if an intervention was already
    // pending before this page loaded, pull its state from the backend.
    fetch(BACKEND_HTTP + '/intervention/status')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && d.pending) openModal(d.message, d.reason); })
      .catch(() => {});

    // WebSocket — auto-reconnect
    let ws = null;
    let reconnectTimer = null;
    const connect = () => {
      try {
        ws = new WebSocket(BACKEND_WS);
      } catch (e) {
        scheduleReconnect();
        return;
      }

      ws.addEventListener('open', () => {
        setStatus('idle');
      });

      ws.addEventListener('message', (evt) => {
        if (evt.data === 'pong') return;
        let msg;
        try { msg = JSON.parse(evt.data); } catch { return; }
        if (!msg || !msg.type) return;

        switch (msg.type) {
          case 'status': {
            const s = msg.data && msg.data.status;
            if (s) setStatus(s);
            break;
          }
          case 'iteration': {
            const d = msg.data || {};
            iterText.textContent = `${d.current || 0} / ${d.max || 0}`;
            const pct = d.max ? Math.min(100, (d.current / d.max) * 100) : 0;
            progressFill.style.width = pct + '%';
            break;
          }
          case 'action': {
            const d = msg.data || {};
            if (d.type === 'start' && d.message) {
              taskEl.textContent = d.message.replace(/^Starting task:\s*/, '');
            }
            if (d.message) actionText.textContent = d.message;
            setStatus('running');
            break;
          }
          case 'intervention_required': {
            const d = msg.data || {};
            openModal(d.message, d.reason);
            break;
          }
          case 'intervention_resolved': {
            closeModal();
            setStatus('running');
            break;
          }
          case 'complete': {
            setStatus('complete');
            actionText.textContent = 'Task complete';
            progressFill.style.width = '100%';
            break;
          }
          case 'error': {
            setStatus('error');
            if (msg.data && msg.data.message) actionText.textContent = msg.data.message;
            break;
          }
          case 'stop_requested': {
            setStatus('stopped');
            actionText.textContent = 'Stop requested…';
            break;
          }
          case 'browser_stopped': {
            setStatus('idle');
            break;
          }
        }
      });

      ws.addEventListener('close', () => {
        setStatus('idle');
        scheduleReconnect();
      });
      ws.addEventListener('error', () => {
        try { ws.close(); } catch {}
      });
    };
    const scheduleReconnect = () => {
      if (reconnectTimer) return;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, 3000);
    };
    connect();
  };

  install();
})();
"""


class BrowserController:
    def __init__(self, headless: bool = False, use_profile: bool = True):
        self.headless = headless
        self.use_profile = use_profile
        self.profile_dir = DEFAULT_PROFILE_DIR
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
        self.pages: List[Page] = []  # Track all open tabs
        self.current_tab_index: int = 0  # Currently active tab
        self.snapshot_cache: Dict[str, Any] = {}
        self._is_persistent_context = False
        self.navigation_history: List[Dict[str, str]] = []  # Track navigation for smart tab decisions
        self.tab_purposes: Dict[int, str] = {}  # Track purpose of each tab
        self._playwright_thread_id = None  # Track which thread owns Playwright context
        
    def start(self):
        """Initialize browser with optional persistent profile"""
        import threading
        self._playwright_thread_id = threading.current_thread().ident
        self.playwright = sync_playwright().start()
        
        # Common browser arguments to improve compatibility
        browser_args = [
            '--start-maximized',
            '--disable-blink-features=AutomationControlled',  # Hide automation
            '--disable-infobars',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-web-security',  # Help with CORS and some loading issues
            '--disable-features=IsolateOrigins,site-per-process',  # Improve compatibility
        ]
        
        # Full user agent string for better compatibility
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        
        if self.use_profile:
            # Use persistent context - this saves cookies, localStorage, credentials
            # Create profile directory if it doesn't exist
            os.makedirs(self.profile_dir, exist_ok=True)
            
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=self.headless,
                args=browser_args,
                no_viewport=True,
                user_agent=user_agent,
                ignore_https_errors=True,
                java_script_enabled=True,
                bypass_csp=True,  # Bypass Content Security Policy
                # Enable permissions for better compatibility
                permissions=['notifications', 'geolocation'],
                # Set longer timeout for slow-loading sites
                slow_mo=50,  # Add small delay between actions for stability
            )
            self._is_persistent_context = True
            self.browser = None  # Persistent context doesn't use separate browser
            
            # Get the first page or create one
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()
        else:
            # Non-persistent context (original behavior)
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=browser_args,
                slow_mo=50,
            )
            self.context = self.browser.new_context(
                no_viewport=True,
                user_agent=user_agent,
                ignore_https_errors=True,
                java_script_enabled=True,
                bypass_csp=True,
                permissions=['notifications', 'geolocation'],
            )
            self.page = self.context.new_page()
            self._is_persistent_context = False
        
        self.pages = [self.page]
        self.current_tab_index = 0

        # Inject the floating agent overlay into every page — current and future,
        # all tabs. add_init_script on the context covers new pages automatically.
        try:
            self.context.add_init_script(script=OVERLAY_SCRIPT)
        except Exception as overlay_err:
            print(f"⚠️  Failed to register overlay init script: {overlay_err}")

        print(f"✓ Browser started {'with persistent profile' if self.use_profile else '(no profile)'}")
        
    def _check_thread_safety(self):
        """Verify we're operating in the same thread that started Playwright"""
        import threading
        current_thread_id = threading.current_thread().ident
        if self._playwright_thread_id and current_thread_id != self._playwright_thread_id:
            raise RuntimeError(
                f"Thread safety violation: Playwright was started in thread {self._playwright_thread_id} "
                f"but is being accessed from thread {current_thread_id}. "
                "All Playwright operations must run in the same thread."
            )
    
    def close(self):
        """Close browser"""
        self._check_thread_safety()
        if self._is_persistent_context:
            if self.context:
                self.context.close()
        else:
            if self.browser:
                self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.pages = []
        self.current_tab_index = 0
        self.context = None
        self.browser = None
        self._is_persistent_context = False
        self._playwright_thread_id = None
        print("✓ Browser closed")
        
    def navigate(self, url: str, purpose: str = None) -> Dict[str, Any]:
        """Navigate to URL with smart waiting"""
        try:
            # Track navigation for autonomous tab management
            self.navigation_history.append({
                'url': url,
                'timestamp': time.time(),
                'tab_index': self.current_tab_index,
                'purpose': purpose or 'navigation'
            })
            self.navigation_history = self.navigation_history[-50:]

            # Update tab purpose if provided
            if purpose:
                self.tab_purposes[self.current_tab_index] = purpose
            
            # Navigate with commit wait - this is more reliable for modern SPAs
            # Use 'commit' instead of 'domcontentloaded' for better reliability
            # Increase timeout for slow-loading sites like Outlook
            self.page.goto(url, wait_until='commit', timeout=60000)
            
            # Wait for body to be visible with longer timeout
            try:
                self.page.wait_for_selector('body', state='visible', timeout=15000)
            except Exception:
                pass  # Some pages may not have body immediately visible

            # Wait for any pending navigation. The auto-snapshot path runs
            # _wait_for_page_ready afterwards, which covers JS init, so we
            # skip the extra fixed 1s sleep.
            try:
                self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            except Exception:
                pass  # Continue even if this times out
            
            return {
                'success': True,
                'url': self.page.url,
                'title': self.page.title()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_interactive_snapshot(self, viewport_only: bool = True) -> Dict[str, Any]:
        """
        Get snapshot of interactive elements on the page via DOM query.

        Single source of truth: we walk the DOM (not the AX tree) because the AX
        tree API was removed from Playwright ≥1.56 and because DOM coverage is
        more predictable across page shapes (forms, link-heavy portals, SPAs).
        """
        try:
            self._wait_for_page_ready()

            interactive_elements = self._get_dom_interactive_elements()

            # Viewport filter (server-side — the JS pass already checks visibility)
            if viewport_only:
                interactive_elements = [
                    e for e in interactive_elements
                    if e.get('rect') and self._is_in_viewport(e['rect'])
                ]

            # Assign nodeIds after filtering so they're contiguous
            for idx, elem in enumerate(interactive_elements):
                elem['nodeId'] = idx

            snapshot_id = int(time.time() * 1000)

            # Full record kept server-side — click/input/etc. need rect + full attrs
            self.snapshot_cache['latest'] = {
                'snapshotId': snapshot_id,
                'timestamp': time.time(),
                'elements': interactive_elements,
            }

            if not interactive_elements:
                return {
                    'success': False,
                    'error': 'No interactive elements found in viewport.',
                    'hint': 'Page may still be loading, or content is outside the viewport. Try viewportOnly=false, scroll, or wait briefly before retrying.',
                    'elements': [],
                }

            # Slim payload returned to the LLM: drop rect, depth, description, empty values
            slim_elements = []
            for e in interactive_elements:
                slim = {
                    'nodeId': e['nodeId'],
                    'type': e['type'],
                    'role': e['role'],
                    'name': e['name'],
                }
                val = (e.get('attributes') or {}).get('value')
                if val:
                    slim['value'] = val
                slim_elements.append(slim)

            return {
                'snapshotId': snapshot_id,
                'elementCount': len(slim_elements),
                'elements': slim_elements,
            }

        except Exception as e:
            logger.warning("get_interactive_snapshot failed: %s", e)
            return {
                'success': False,
                'error': str(e),
                'hint': 'Page may be navigating. Wait briefly and retry getInteractiveSnapshot.',
                'elements': []
            }
    
    def _get_dom_interactive_elements(self) -> List[Dict]:
        """
        Single DOM pass that collects every interactive element on the page:
        form fields, links, buttons, and anything carrying an interactive ARIA
        role or click affordance. Visibility-filtered (rect > 0, not hidden).
        """
        try:
            raw_elements = self.page.evaluate('''() => {
                const results = [];
                const seenRects = new Set();
                const seenEls = new WeakSet();

                const CLICKABLE_ROLES = new Set([
                    'button', 'link', 'checkbox', 'radio', 'switch',
                    'menuitem', 'menuitemcheckbox', 'menuitemradio',
                    'tab', 'option', 'treeitem', 'gridcell'
                ]);
                const TYPEABLE_ROLES = new Set([
                    'textbox', 'searchbox', 'spinbutton'
                ]);
                const SELECTABLE_ROLES = new Set([
                    'combobox', 'listbox', 'menu'
                ]);

                function isVisible(el, rect) {
                    if (rect.width < 4 || rect.height < 4) return false;
                    const style = window.getComputedStyle(el);
                    if (style.visibility === 'hidden' || style.display === 'none') return false;
                    if (parseFloat(style.opacity) < 0.05) return false;
                    return true;
                }

                function computeName(el, labelOverride) {
                    if (labelOverride) return labelOverride;

                    const aria = el.getAttribute('aria-label');
                    if (aria) return aria.trim();

                    const labelledby = el.getAttribute('aria-labelledby');
                    if (labelledby) {
                        const ref = document.getElementById(labelledby.split(/\\s+/)[0]);
                        if (ref && ref.textContent) return ref.textContent.trim();
                    }

                    if (el.id) {
                        const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                        if (lbl && lbl.textContent) return lbl.textContent.trim();
                    }

                    const closestLabel = el.closest('label');
                    if (closestLabel && closestLabel.textContent) {
                        return closestLabel.textContent.trim();
                    }

                    const placeholder = el.getAttribute('placeholder') || el.getAttribute('data-placeholder');
                    if (placeholder) return placeholder.trim();

                    // For links/buttons, prefer visible text
                    if (el.tagName === 'A' || el.tagName === 'BUTTON' ||
                        ['button', 'link', 'menuitem', 'tab'].includes(el.getAttribute('role'))) {
                        const text = (el.innerText || el.textContent || '').trim();
                        if (text) return text;
                        const title = el.getAttribute('title');
                        if (title) return title.trim();
                        const img = el.querySelector('img[alt]');
                        if (img) return (img.getAttribute('alt') || '').trim();
                    }

                    return (el.getAttribute('name') ||
                            el.getAttribute('title') ||
                            el.value ||
                            '').toString().trim();
                }

                function resolveRole(el) {
                    const explicit = el.getAttribute('role');
                    if (explicit) return explicit;

                    const tag = el.tagName;
                    if (tag === 'A' && el.hasAttribute('href')) return 'link';
                    if (tag === 'BUTTON') return 'button';
                    if (tag === 'SELECT') return 'combobox';
                    if (tag === 'TEXTAREA') return 'textbox';
                    if (tag === 'INPUT') {
                        const t = (el.type || 'text').toLowerCase();
                        if (t === 'checkbox') return 'checkbox';
                        if (t === 'radio') return 'radio';
                        if (t === 'submit' || t === 'button' || t === 'reset') return 'button';
                        if (t === 'search') return 'searchbox';
                        return 'textbox';
                    }
                    if (el.hasAttribute('contenteditable')) return 'textbox';
                    return '';
                }

                function addElement(el, labelOverride = null) {
                    if (seenEls.has(el)) return;
                    const rect = el.getBoundingClientRect();
                    if (!isVisible(el, rect)) return;

                    const rectKey = `${Math.round(rect.x)},${Math.round(rect.y)},${Math.round(rect.width)},${Math.round(rect.height)}`;
                    if (seenRects.has(rectKey)) return;

                    const role = resolveRole(el);
                    if (!role) return;

                    seenEls.add(el);
                    seenRects.add(rectKey);

                    const name = (computeName(el, labelOverride) || '').substring(0, 120);
                    const inputType = (el.type || '').toLowerCase();

                    results.push({
                        tagName: el.tagName.toLowerCase(),
                        role,
                        name,
                        inputType,
                        value: (el.value || '').toString().substring(0, 80),
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        checked: el.checked === true || el.getAttribute('aria-checked') === 'true',
                        isDate: inputType === 'date' ||
                                /date|birth|dob/i.test(name)
                    });
                }

                // 1. Form controls
                document.querySelectorAll('input, textarea, select').forEach(el => addElement(el));

                // 2. Links and buttons (post-login pages are mostly these)
                document.querySelectorAll('a[href], button').forEach(el => addElement(el));

                // 3. Elements with interactive ARIA roles
                const roleSelector = [...CLICKABLE_ROLES, ...TYPEABLE_ROLES, ...SELECTABLE_ROLES]
                    .map(r => `[role="${r}"]`).join(',');
                document.querySelectorAll(roleSelector).forEach(el => addElement(el));

                // 4. Contenteditable + tabindex-based interactives
                document.querySelectorAll('[contenteditable="true"], [contenteditable=""]').forEach(el => addElement(el));
                document.querySelectorAll('[tabindex="0"], [onclick]').forEach(el => {
                    if ((el.innerText || el.textContent || '').trim()) addElement(el);
                });

                // 5. Google-Forms / Sakai-style labelled question containers
                document.querySelectorAll('[role="listitem"]').forEach(container => {
                    const heading = container.querySelector('[role="heading"]');
                    const label = heading?.textContent?.trim() || '';
                    if (!label) return;
                    container.querySelectorAll(
                        'input, textarea, [role="textbox"], [role="listbox"], [role="combobox"], [role="radio"], [role="checkbox"], [data-value]'
                    ).forEach(el => addElement(el, label));
                });

                return results;
            }''')

            # Convert to our element format
            result_elements = []
            for elem in raw_elements or []:
                role = elem.get('role') or 'button'
                input_type = (elem.get('inputType') or '').lower()
                tag = elem.get('tagName', '')

                if role in ('checkbox', 'radio', 'switch'):
                    elem_type = 'clickable'
                elif role in ('textbox', 'searchbox', 'spinbutton') and (input_type == 'date' or elem.get('isDate')):
                    elem_type = 'date-input'
                elif role in ('textbox', 'searchbox', 'spinbutton'):
                    elem_type = 'typeable'
                elif role in ('combobox', 'listbox', 'menu'):
                    elem_type = 'selectable'
                elif role in ('button', 'link', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
                              'tab', 'option', 'treeitem', 'gridcell'):
                    elem_type = 'clickable'
                else:
                    elem_type = 'clickable'

                name = elem.get('name') or ''
                if not name:
                    # Skip truly nameless elements — they're not useful to the LLM
                    continue

                result_elements.append({
                    'type': elem_type,
                    'name': name,
                    'role': role,
                    'rect': elem.get('rect'),
                    'attributes': {
                        'value': elem.get('value', ''),
                        'description': f"DOM element: {tag}",
                        'depth': 0,
                        'isDate': elem.get('isDate', False),
                        'tagName': tag,
                        'inputType': input_type or role,
                        'checked': elem.get('checked', False),
                    }
                })

            return result_elements

        except Exception as e:
            logger.warning("Error getting DOM interactive elements: %s", e)
            return []
    
    def _is_in_viewport(self, rect: Dict) -> bool:
        """Check if element is in viewport"""
        viewport = self.page.viewport_size
        
        # If no viewport is set (no_viewport=True), get window size instead
        if viewport is None:
            viewport = self.page.evaluate('''() => ({
                width: window.innerWidth,
                height: window.innerHeight
            })''')
        
        return (
            rect['x'] >= 0 and 
            rect['y'] >= 0 and
            rect['x'] < viewport['width'] and
            rect['y'] < viewport['height']
        )
    
    def _build_hierarchy(self, elements: List[Dict]) -> str:
        """Build text hierarchy of elements for LLM context"""
        lines = []
        for elem in elements:
            indent = "  " * elem['attributes'].get('depth', 0)
            name = elem['name'] or '[no name]'
            lines.append(f"{indent}- {elem['role']}: {name} (nodeId: {elem['nodeId']})")
        return "\n".join(lines[:50])  # Limit to avoid token overflow
    
    def click(self, node_id: int, verify_action: bool = True) -> Dict[str, Any]:
        """
        Click on element by nodeId with optional state verification

        Args:
            node_id: The nodeId to click
            verify_action: If True, checks element state before clicking to avoid double-toggles
        """
        try:
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available. Call getInteractiveSnapshot first.'}

            # Find element
            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {
                    'success': False,
                    'error': f'nodeId {node_id} not in current snapshot.',
                    'hint': 'Snapshot may be stale after DOM changed. Call getInteractiveSnapshot to refresh nodeIds.',
                }

            # Check state before clicking if it's a toggle element
            pre_state = None
            if verify_action and element['role'] in ['checkbox', 'radio', 'switch']:
                pre_state = self.get_element_state(node_id)
                if pre_state.get('checked'):
                    print(f"    ℹ️  Element {node_id} is already checked, skipping click")
                    return {
                        'success': True,
                        'message': 'Already in desired state',
                        'skipped': True,
                        'state': pre_state
                    }

            # Try different click strategies, recording why each fails
            clicked = False
            strategy_errors: Dict[str, str] = {}

            # Strategy 1: Click by role and name
            if element['name']:
                try:
                    locator = self.page.get_by_role(element['role'], name=element['name'], exact=False)
                    if locator.count() > 0:
                        locator.first.wait_for(state='visible', timeout=5000)
                        locator.first.click(timeout=5000)
                        clicked = True
                    else:
                        strategy_errors['role_name'] = 'no match'
                except Exception as e:
                    strategy_errors['role_name'] = str(e)[:120]
                    print(f"    Strategy 1 failed: {e}")

            # Strategy 2: Click by coordinates
            if not clicked and element['rect']:
                try:
                    x = element['rect']['x'] + element['rect']['width'] / 2
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    self.page.mouse.click(x, y)
                    clicked = True
                except Exception as e:
                    strategy_errors['coords'] = str(e)[:120]
                    print(f"    Strategy 2 failed: {e}")

            # Strategy 3: Click by text
            if not clicked and element['name']:
                try:
                    self.page.get_by_text(element['name'], exact=False).first.click(timeout=5000)
                    clicked = True
                except Exception as e:
                    strategy_errors['text'] = str(e)[:120]
                    print(f"    Strategy 3 failed: {e}")

            # Smart wait after click — short load-state poll; skip the long
            # fallback sleep, since the auto-snapshot will trigger its own
            # readiness wait anyway.
            post_state = None
            if clicked:
                try:
                    self.page.wait_for_load_state('domcontentloaded', timeout=1000)
                except Exception:
                    pass

                if verify_action and element['role'] in ['checkbox', 'radio', 'switch'] and pre_state:
                    post_state = self.get_element_state(node_id)

            result: Dict[str, Any] = {'success': clicked}
            if not clicked:
                result['error'] = f'Could not click "{element["name"]}" ({element["role"]})'
                result['strategies_tried'] = strategy_errors
                result['hint'] = 'Element may have been removed or replaced. Try clickByText with its label, or refresh with getInteractiveSnapshot.'
            if pre_state:
                result['pre_state'] = pre_state
            if post_state:
                result['post_state'] = post_state

            return result

        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def input_text(self, node_id: int, text: str) -> Dict[str, Any]:
        """Input text into element with verification and one retry on verify-fail."""
        try:
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available. Call getInteractiveSnapshot first.'}

            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {
                    'success': False,
                    'error': f'nodeId {node_id} not in current snapshot.',
                    'hint': 'Snapshot may be stale. Call getInteractiveSnapshot to refresh nodeIds.',
                }

            def verify_value_set() -> Optional[bool]:
                """Return True/False if we can verify, or None if we can't."""
                if not element.get('rect'):
                    return None
                try:
                    r = self.page.evaluate(f'''() => {{
                        const inputs = document.querySelectorAll('input, textarea, [contenteditable="true"]');
                        for (const input of inputs) {{
                            const rect = input.getBoundingClientRect();
                            if (Math.abs(rect.x - {element['rect']['x']}) < 20 &&
                                Math.abs(rect.y - {element['rect']['y']}) < 20) {{
                                const value = input.value || input.textContent || '';
                                return value.length > 0;
                            }}
                        }}
                        return null;
                    }}''')
                    return None if r is None else bool(r)
                except Exception:
                    return None

            filled = False
            strategies_tried = []

            # Strategy 1: By role and name
            if element['name']:
                try:
                    locator = self.page.get_by_role(element['role'], name=element['name'], exact=False)
                    if locator.count() > 0:
                        locator.first.wait_for(state='visible', timeout=5000)
                        locator.first.fill(text)
                        filled = True
                        strategies_tried.append('role_name')
                except Exception:
                    pass

            # Strategy 2: By label
            if not filled and element['name']:
                try:
                    self.page.get_by_label(element['name'], exact=False).first.fill(text)
                    filled = True
                    strategies_tried.append('label')
                except Exception:
                    pass

            # Strategy 3: Click at coordinates then type
            if not filled and element['rect']:
                try:
                    x = element['rect']['x'] + element['rect']['width'] / 2
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    self.page.mouse.click(x, y)
                    time.sleep(0.2)
                    self.page.keyboard.press('Control+A')
                    time.sleep(0.1)
                    self.page.keyboard.type(text)
                    filled = True
                    strategies_tried.append('click_type')
                except Exception:
                    pass

            if not filled:
                return {
                    'success': False,
                    'error': f'All input strategies failed for "{element["name"]}" ({element["role"]})',
                    'hint': 'Field may be read-only or hidden. Try clicking it first, or refresh via getInteractiveSnapshot.',
                }

            # Allow input handlers to process, then verify.
            self.page.wait_for_timeout(300)
            verified = verify_value_set()

            # If verification says the value didn't stick, retry once with click+type.
            if verified is False and 'click_type' not in strategies_tried and element.get('rect'):
                print(f"    ⚠️  Verification failed — retrying with click+type")
                try:
                    x = element['rect']['x'] + element['rect']['width'] / 2
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    self.page.mouse.click(x, y)
                    time.sleep(0.2)
                    self.page.keyboard.press('Control+A')
                    time.sleep(0.1)
                    self.page.keyboard.type(text)
                    strategies_tried.append('click_type_retry')
                    self.page.wait_for_timeout(300)
                    verified = verify_value_set()
                except Exception:
                    pass

            if verified is False:
                return {
                    'success': False,
                    'error': 'Text did not stick after retry — field may be a custom widget or reject programmatic input.',
                    'strategies_tried': strategies_tried,
                    'hint': 'Try click(nodeId) first, then sendKeys to type each character, or look for a custom input method.',
                }

            # verified is True or None (can't tell) — treat as success
            return {'success': True, 'strategies_tried': strategies_tried}

        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_for_form_errors(self) -> Dict[str, Any]:
        """
        Check if there are any visible form validation errors on the page.
        Returns error messages if found.
        """
        try:
            errors = self.page.evaluate('''() => {
                const errorMessages = [];
                
                // Common error selectors
                const errorSelectors = [
                    '[role="alert"]',
                    '.error-message',
                    '.error',
                    '.validation-error',
                    '[aria-invalid="true"]',
                    '.invalid-feedback',
                    // Google Forms specific
                    '.freebirdFormviewerComponentsQuestionBaseRoot.hasError',
                    '[data-error-message]',
                    '.errorHeader'
                ];
                
                // Check for elements with "error" or "required" text that are visible
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent?.toLowerCase() || '';
                    const style = window.getComputedStyle(el);
                    
                    // Skip hidden elements
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    
                    // Check for common error patterns
                    if ((text.includes('required') || text.includes('invalid') || text.includes('error')) &&
                        el.offsetHeight > 0 && el.offsetHeight < 100) {
                        // Check if it's actually an error message (red color, small element)
                        const color = style.color;
                        if (color.includes('rgb(2') || color.includes('red') || el.classList.contains('error')) {
                            const cleanText = el.textContent?.trim();
                            if (cleanText && cleanText.length < 200 && !errorMessages.includes(cleanText)) {
                                errorMessages.push(cleanText);
                            }
                        }
                    }
                }
                
                // Also check for specific error selectors
                for (const selector of errorSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            if (el.offsetHeight > 0) {
                                const text = el.textContent?.trim() || el.getAttribute('data-error-message');
                                if (text && text.length < 200 && !errorMessages.includes(text)) {
                                    errorMessages.push(text);
                                }
                            }
                        });
                    } catch (e) {}
                }
                
                return errorMessages;
            }''')
            
            return {
                'hasErrors': len(errors) > 0,
                'errors': errors[:5],  # Limit to 5 errors
                'message': f"Found {len(errors)} error(s)" if errors else "No errors found"
            }
            
        except Exception as e:
            return {'hasErrors': False, 'errors': [], 'error': str(e)}

    def get_page_signals(self) -> Dict[str, Any]:
        """
        Lightweight scan for page-level feedback signals: validation errors, required empty fields, success notices.
        Returns empty lists if nothing found. Used to give the LLM context about what the page is showing.
        """
        try:
            signals = self.page.evaluate('''() => {
                const errors = [];
                const required_empty = [];
                const notices = [];

                // === ERRORS ===
                // 1. ARIA alert role
                document.querySelectorAll('[role="alert"]').forEach(el => {
                    const text = el.textContent?.trim();
                    if (text && text.length < 200) errors.push(text);
                });

                // 2. aria-invalid
                document.querySelectorAll('[aria-invalid="true"]').forEach(el => {
                    const label = el.getAttribute('aria-label') || el.getAttribute('aria-describedby');
                    if (label) errors.push(label);
                });

                // 3. Error message classes
                document.querySelectorAll('.error, .error-message, .validation-error, .invalid-feedback, [data-error-message]').forEach(el => {
                    const text = el.textContent?.trim();
                    if (text && text.length < 200 && el.offsetParent) {
                        errors.push(text);
                    }
                });

                // 4. Red-ish text with error keywords
                const errorKeywords = /error|invalid|required|must|please|fail|wrong/i;
                document.querySelectorAll('*').forEach(el => {
                    const text = el.textContent?.trim() || '';
                    if (errorKeywords.test(text) && text.length < 200 && text.length > 5 && el.offsetParent) {
                        const color = window.getComputedStyle(el).color;
                        if (color.match(/rgb\\((1[0-9]{2}|2[0-4][0-9]|25[0-5]),\\s*([0-9]{1,2}|[0-9]{1,2}),/)) {
                            if (!errors.includes(text)) errors.push(text);
                        }
                    }
                });

                // === REQUIRED EMPTY FIELDS ===
                document.querySelectorAll('input[required], textarea[required], select[required], [aria-required="true"]').forEach(el => {
                    if (el.offsetParent && (el.value === '' || el.value === null)) {
                        const label = el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
                                     document.querySelector(`label[for="${el.id}"]`)?.textContent?.trim() ||
                                     el.name || 'Field';
                        required_empty.push(label);
                    }
                });

                // === NOTICES (Success/Status) ===
                // 1. ARIA status
                document.querySelectorAll('[role="status"]').forEach(el => {
                    const text = el.textContent?.trim();
                    if (text && text.length < 200) notices.push(text);
                });

                // 2. Success message classes
                document.querySelectorAll('.success, .alert-success, .success-message, .confirmation, [data-success]').forEach(el => {
                    const text = el.textContent?.trim();
                    if (text && text.length < 200 && el.offsetParent && !notices.includes(text)) {
                        notices.push(text);
                    }
                });

                // 3. Green-ish text with success keywords
                const successKeywords = /success|complete|posted|saved|confirmed|done|processed/i;
                document.querySelectorAll('*').forEach(el => {
                    const text = el.textContent?.trim() || '';
                    if (successKeywords.test(text) && text.length < 200 && text.length > 5 && el.offsetParent) {
                        const color = window.getComputedStyle(el).color;
                        if (color.match(/rgb\\(([0-9]{1,2}),\\s*(1[0-9]{2}|2[0-4][0-9]|25[0-5]),/)) {
                            if (!notices.includes(text)) notices.push(text);
                        }
                    }
                });

                // Deduplicate and limit
                const dedup = (arr) => [...new Set(arr)].slice(0, 5);

                return {
                    errors: dedup(errors),
                    required_empty: dedup(required_empty),
                    notices: dedup(notices).slice(0, 3),
                    has_signals: errors.length > 0 || required_empty.length > 0 || notices.length > 0
                };
            }''')
            return signals
        except Exception as e:
            logger.warning(f"Failed to scan page signals: {e}")
            return {'errors': [], 'required_empty': [], 'notices': [], 'has_signals': False}

    def click_by_text(self, text: str, element_type: str = 'any') -> Dict[str, Any]:
        """
        Click on an element by its visible text content.
        More reliable than nodeId for buttons like "Next", "Submit", etc.
        
        Args:
            text: The visible text to click (e.g., "Next", "Submit", "Sign in")
            element_type: Type of element - 'button', 'link', or 'any'
        """
        try:
            clicked = False
            
            # Strategy 1: By role (most reliable for buttons)
            if element_type in ['button', 'any']:
                try:
                    locator = self.page.get_by_role('button', name=text, exact=False)
                    if locator.count() > 0:
                        locator.first.wait_for(state='visible', timeout=3000)
                        locator.first.click(timeout=5000)
                        clicked = True
                except Exception as e:
                    print(f"    Button role click failed: {e}")
            
            # Strategy 2: By link role
            if not clicked and element_type in ['link', 'any']:
                try:
                    locator = self.page.get_by_role('link', name=text, exact=False)
                    if locator.count() > 0:
                        locator.first.wait_for(state='visible', timeout=3000)
                        locator.first.click(timeout=5000)
                        clicked = True
                except Exception as e:
                    print(f"    Link role click failed: {e}")
            
            # Strategy 3: By text content directly
            if not clicked:
                try:
                    locator = self.page.get_by_text(text, exact=False)
                    if locator.count() > 0:
                        locator.first.wait_for(state='visible', timeout=3000)
                        locator.first.click(timeout=5000)
                        clicked = True
                except Exception as e:
                    print(f"    Text click failed: {e}")
            
            # Strategy 4: CSS selector with text
            if not clicked:
                try:
                    # Try common button selectors
                    selectors = [
                        f'button:has-text("{text}")',
                        f'[role="button"]:has-text("{text}")',
                        f'input[value="{text}"]',
                        f'a:has-text("{text}")',
                        f'span:has-text("{text}")'
                    ]
                    for selector in selectors:
                        try:
                            self.page.click(selector, timeout=2000)
                            clicked = True
                            break
                        except:
                            continue
                except Exception as e:
                    print(f"    Selector click failed: {e}")
            
            # Wait for page to respond — short poll; auto-snapshot handles final readiness.
            if clicked:
                try:
                    self.page.wait_for_load_state('domcontentloaded', timeout=1500)
                except Exception:
                    pass
            
            return {
                'success': clicked,
                'message': f'Clicked "{text}"' if clicked else f'Could not find clickable element with text "{text}"'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def select_date(self, node_id: int, date_string: str) -> Dict[str, Any]:
        """
        Select a date in a date picker element
        Handles various date picker formats (native HTML5, Google Forms, etc.)
        
        Args:
            node_id: The nodeId of the date input element
            date_string: Date in format "YYYY-MM-DD" or "MM/DD/YYYY" or "DD/MM/YYYY"
        """
        try:
            from datetime import datetime
            
            self.page.wait_for_timeout(300)
            
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available. Call getInteractiveSnapshot first.'}

            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {
                    'success': False,
                    'error': f'nodeId {node_id} not in current snapshot.',
                    'hint': 'Snapshot may be stale. Call getInteractiveSnapshot to refresh nodeIds.',
                }

            # Parse date to ensure correct format
            date_obj = None
            try:
                if '-' in date_string and len(date_string.split('-')[0]) == 4:
                    date_obj = datetime.strptime(date_string, "%Y-%m-%d")
                elif '/' in date_string:
                    parts = date_string.split('/')
                    if len(parts[0]) == 4:
                        date_obj = datetime.strptime(date_string, "%Y/%m/%d")
                    elif int(parts[0]) > 12:  # DD/MM/YYYY
                        date_obj = datetime.strptime(date_string, "%d/%m/%Y")
                    else:  # MM/DD/YYYY
                        date_obj = datetime.strptime(date_string, "%m/%d/%Y")
                else:
                    date_obj = datetime.strptime(date_string, "%Y-%m-%d")
            except Exception as parse_err:
                print(f"    Date parse warning: {parse_err}")
                pass
            
            if not date_obj:
                return {'success': False, 'error': f'Could not parse date: {date_string}'}
            
            selected = False
            formatted_date = date_obj.strftime("%Y-%m-%d")
            
            # Strategy 1: Use JavaScript to directly set value on the date input
            if not selected and element['rect']:
                try:
                    result = self.page.evaluate(f'''() => {{
                        // Find date input by position
                        const inputs = document.querySelectorAll('input[type="date"]');
                        for (const input of inputs) {{
                            const rect = input.getBoundingClientRect();
                            if (Math.abs(rect.x - {element['rect']['x']}) < 20 && 
                                Math.abs(rect.y - {element['rect']['y']}) < 20) {{
                                input.value = "{formatted_date}";
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                return {{ success: true, value: input.value }};
                            }}
                        }}
                        return {{ success: false, error: 'Date input not found by position' }};
                    }}''')
                    if result.get('success') and result.get('value') == formatted_date:
                        selected = True
                        print(f"    ✓ Date set via JavaScript: {formatted_date}")
                except Exception as e:
                    print(f"    Strategy 1 (JavaScript by position) failed: {e}")
            
            # Strategy 2: Click and type using Tab navigation (works for many date inputs)
            if not selected and element['rect']:
                try:
                    x = element['rect']['x'] + 20  # Click near the start of the field
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    
                    # Click to focus
                    self.page.mouse.click(x, y)
                    self.page.wait_for_timeout(300)
                    
                    # Select all and clear
                    self.page.keyboard.press('Control+A')
                    self.page.wait_for_timeout(100)
                    
                    # Type month
                    self.page.keyboard.type(str(date_obj.month).zfill(2))
                    self.page.wait_for_timeout(100)
                    
                    # Tab to day (more reliable than ArrowRight)
                    self.page.keyboard.press('Tab')
                    self.page.wait_for_timeout(100)
                    
                    # Type day
                    self.page.keyboard.type(str(date_obj.day).zfill(2))
                    self.page.wait_for_timeout(100)
                    
                    # Tab to year
                    self.page.keyboard.press('Tab')
                    self.page.wait_for_timeout(100)
                    
                    # Type year
                    self.page.keyboard.type(str(date_obj.year))
                    self.page.wait_for_timeout(200)
                    
                    # Blur to confirm
                    self.page.keyboard.press('Tab')
                    self.page.wait_for_timeout(300)
                    
                    print(f"    ✓ Date entered via keyboard Tab: {date_obj.month:02d}/{date_obj.day:02d}/{date_obj.year}")
                    selected = True
                except Exception as e:
                    print(f"    Strategy 2 (keyboard Tab) failed: {e}")
            
            # Strategy 3: For Google Forms - look for Month/Day/Year spinbuttons in snapshot
            if not selected:
                try:
                    month_elem = next((e for e in snapshot['elements'] if 'Month' in (e.get('name') or '')), None)
                    day_elem = next((e for e in snapshot['elements'] if 'Day' in (e.get('name') or '') and 'birth' not in (e.get('name') or '').lower()), None)
                    year_elem = next((e for e in snapshot['elements'] if 'Year' in (e.get('name') or '')), None)
                    
                    if month_elem or day_elem or year_elem:
                        print(f"    Found Google Forms date spinbuttons, using direct input...")
                        
                        # Use JavaScript to find and fill the Google Forms date fields
                        result = self.page.evaluate(f'''() => {{
                            // Google Forms uses specific structure for date inputs
                            const dateContainers = document.querySelectorAll('[data-params*="date" i], [aria-label*="date" i], [aria-label*="birth" i]');
                            
                            // Try to find input fields near the target
                            const allInputs = document.querySelectorAll('input');
                            let filled = false;
                            
                            for (const input of allInputs) {{
                                const rect = input.getBoundingClientRect();
                                // Check if this input is near our target element
                                if (Math.abs(rect.y - {element['rect']['y']}) < 50) {{
                                    if (input.type === 'date') {{
                                        input.value = "{formatted_date}";
                                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        filled = true;
                                        break;
                                    }}
                                }}
                            }}
                            
                            return {{ success: filled }};
                        }}''')
                        
                        if result.get('success'):
                            selected = True
                            print(f"    ✓ Google Forms date filled: {formatted_date}")
                except Exception as e:
                    print(f"    Strategy 3 (Google Forms spinbuttons) failed: {e}")
            
            # Strategy 4: Direct locator fill as last resort
            if not selected and element['name']:
                try:
                    # Try clicking the date input first
                    if element['rect']:
                        self.page.mouse.click(
                            element['rect']['x'] + element['rect']['width'] / 2,
                            element['rect']['y'] + element['rect']['height'] / 2
                        )
                        self.page.wait_for_timeout(300)
                    
                    # Try to find and fill any visible date input
                    date_input = self.page.locator('input[type="date"]').first
                    if date_input.is_visible(timeout=1000):
                        date_input.fill(formatted_date)
                        selected = True
                        print(f"    ✓ Date filled via locator: {formatted_date}")
                except Exception as e:
                    print(f"    Strategy 4 (locator) failed: {e}")
            
            # VERIFY the date was actually entered
            if selected:
                try:
                    self.page.wait_for_timeout(500)
                    # Check if the value was actually set
                    verify_result = self.page.evaluate(f'''() => {{
                        const inputs = document.querySelectorAll('input[type="date"]');
                        for (const input of inputs) {{
                            const rect = input.getBoundingClientRect();
                            if (Math.abs(rect.x - {element['rect']['x']}) < 20 && 
                                Math.abs(rect.y - {element['rect']['y']}) < 20) {{
                                return {{ value: input.value, hasValue: input.value.length > 0 }};
                            }}
                        }}
                        return {{ value: '', hasValue: false }};
                    }}''')
                    
                    if not verify_result.get('hasValue'):
                        print(f"    ⚠️  Date verification failed - value not set!")
                        selected = False
                except:
                    pass
            
            return {
                'success': selected,
                'message': f'Date {"selected" if selected else "NOT selected (verification failed)"}: {formatted_date}',
                'date': formatted_date
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def upload_file_to_input(self, node_id: int, file_path: str) -> Dict[str, Any]:
        """Upload a local file to a <input type='file'> element identified by nodeId.

        After calling this, the LLM should check the page for a confirmation button
        (e.g. 'Upload', 'Attach', 'Done') and click it — many sites require an explicit
        confirm step before the file is truly attached.
        """
        try:
            if not os.path.exists(file_path):
                return {'success': False, 'error': f'File not found on disk: {file_path}'}

            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available. Call getInteractiveSnapshot first.'}

            element = next((e for e in snapshot.get('elements', []) if e['nodeId'] == node_id), None)
            if not element:
                return {'success': False, 'error': f'Element with nodeId {node_id} not found in snapshot'}

            # Collect all file inputs on the page (including hidden ones used by custom widgets)
            file_inputs = self.page.locator('input[type="file"]')
            count = file_inputs.count()
            if count == 0:
                return {'success': False, 'error': 'No <input type="file"> elements found on this page'}

            # Try to match by accessible name / label text, then fall back to first input
            label = element.get('name', '') or element.get('label', '') or element.get('text', '')
            target = None
            if label:
                for i in range(count):
                    inp = file_inputs.nth(i)
                    try:
                        aria = inp.get_attribute('aria-label') or ''
                        id_attr = inp.get_attribute('id') or ''
                        name_attr = inp.get_attribute('name') or ''
                        if label.lower() in (aria + id_attr + name_attr).lower():
                            target = inp
                            break
                    except Exception:
                        pass

            if target is None:
                target = file_inputs.first

            # Use Playwright's expect_file_chooser to handle sites that open a file picker
            # dialog on button click. set_input_files works for both hidden inputs and choosers.
            target.set_input_files(file_path)

            # Dispatch change + input events explicitly — some JS frameworks (React, Vue, Sakai)
            # do not react to programmatic value changes without these events
            try:
                target.dispatch_event('change')
                target.dispatch_event('input')
            except Exception:
                pass

            # Give the UI time to process the file selection
            self.page.wait_for_timeout(1500)

            file_name = os.path.basename(file_path)
            return {
                'success': True,
                'message': (
                    f'File "{file_name}" set on the file input. '
                    'IMPORTANT: Many sites require an additional step — look for and click an '
                    '"Upload", "Attach", "Add", "Continue", or "Done" button to confirm the upload. '
                    'Call getInteractiveSnapshot to check what buttons are now available.'
                ),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_element_state(self, node_id: int) -> Dict[str, Any]:
        """
        Get the current state of an element (checked, selected, value, etc.)
        Useful to avoid double-toggling checkboxes/radios
        """
        try:
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available. Call getInteractiveSnapshot first.'}

            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {
                    'success': False,
                    'error': f'nodeId {node_id} not in current snapshot.',
                    'hint': 'Snapshot may be stale. Call getInteractiveSnapshot to refresh nodeIds.',
                }

            state_info = {'success': True, 'nodeId': node_id, 'role': element['role']}
            
            # Try to get element state
            try:
                if element['name']:
                    locator = self.page.get_by_role(element['role'], name=element['name'], exact=False)
                    if locator.count() > 0:
                        elem = locator.first
                        
                        # Check if it's a checkbox or radio
                        if element['role'] in ['checkbox', 'radio']:
                            try:
                                is_checked = elem.is_checked(timeout=1000)
                                state_info['checked'] = is_checked
                            except:
                                state_info['checked'] = None
                        
                        # Get aria attributes
                        try:
                            aria_checked = elem.get_attribute('aria-checked', timeout=1000)
                            state_info['aria_checked'] = aria_checked
                        except:
                            pass
                        
                        # Get value
                        try:
                            value = elem.input_value(timeout=1000)
                            state_info['value'] = value
                        except:
                            pass
                        
                        # Check if disabled
                        try:
                            is_disabled = elem.is_disabled(timeout=1000)
                            state_info['disabled'] = is_disabled
                        except:
                            pass
            except Exception as e:
                state_info['error'] = str(e)
            
            return state_info
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def select_dropdown_option(self, node_id: int, option_text: str) -> Dict[str, Any]:
        """
        Select an option from a dropdown/combobox by text
        Better than click for dropdown menus
        """
        try:
            self.page.wait_for_timeout(300)
            
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available. Call getInteractiveSnapshot first.'}

            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {
                    'success': False,
                    'error': f'nodeId {node_id} not in current snapshot.',
                    'hint': 'Snapshot may be stale. Call getInteractiveSnapshot to refresh nodeIds.',
                }

            selected = False

            # Strategy 1: Native select element
            try:
                if element['name']:
                    locator = self.page.get_by_role(element['role'], name=element['name'], exact=False)
                    if locator.count() > 0:
                        locator.first.select_option(label=option_text)
                        selected = True
            except Exception as e:
                print(f"    Select strategy 1 failed: {e}")
            
            # Strategy 2: Click dropdown then click option
            if not selected:
                try:
                    # Click to open dropdown
                    click_result = self.click(node_id)
                    if click_result.get('success'):
                        self.page.wait_for_timeout(500)
                        
                        # Find and click the option
                        option_selectors = [
                            f'[role="option"]:has-text("{option_text}")',
                            f'[role="menuitem"]:has-text("{option_text}")',
                            f'li:has-text("{option_text}")',
                            f'.option:has-text("{option_text}")'
                        ]
                        
                        for selector in option_selectors:
                            try:
                                self.page.click(selector, timeout=2000)
                                selected = True
                                break
                            except:
                                continue
                except Exception as e:
                    print(f"    Select strategy 2 failed: {e}")
            
            if selected:
                self.page.wait_for_timeout(300)
            
            return {'success': selected}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def scroll_down(self) -> Dict[str, bool]:
        """Scroll down by viewport height"""
        try:
            self.page.evaluate('window.scrollBy(0, window.innerHeight * 0.8)')
            time.sleep(0.1)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def scroll_up(self) -> Dict[str, bool]:
        """Scroll up by viewport height"""
        try:
            self.page.evaluate('window.scrollBy(0, -window.innerHeight * 0.8)')
            time.sleep(0.1)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_page_content(self) -> Dict[str, str]:
        """Get text content of page"""
        try:
            content = self.page.inner_text('body')
            # Limit content to avoid token overflow
            if len(content) > 10000:
                content = content[:10000] + "... [truncated]"
            
            return {
                'content': content,
                'title': self.page.title(),
                'url': self.page.url
            }
        except Exception as e:
            return {'error': str(e)}
    
    def capture_screenshot(self, full_page: bool = False) -> Dict[str, str]:
        """Capture screenshot and return base64"""
        try:
            screenshot_bytes = self.page.screenshot(full_page=full_page)
            base64_image = base64.b64encode(screenshot_bytes).decode()
            return {'dataUrl': f'data:image/png;base64,{base64_image}'}
        except Exception as e:
            return {'error': str(e)}
    
    def send_keys(self, key: str) -> Dict[str, bool]:
        """Send special keys"""
        try:
            self.page.keyboard.press(key)
            time.sleep(0.2)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _wait_for_page_ready(self, timeout: int = 30000):
        """Fast readiness check. Exits as soon as the DOM is quiet, capped
        at ~600ms for stable pages and ~1.2s for churny ones — instead of
        the unconditional 2s MutationObserver window we used to use."""
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=timeout)

            # Short mutation-settle probe: 150ms of inactivity = "ready",
            # hard-cap at 600ms. SPAs that keep mutating still get a second
            # chance up to ~1.2s via the fallback wait below.
            stable = self.page.evaluate(
                '''() => new Promise((resolve) => {
                    let lastChange = performance.now();
                    const observer = new MutationObserver(() => {
                        lastChange = performance.now();
                    });
                    observer.observe(document.body || document.documentElement, {
                        childList: true, subtree: true
                    });
                    const start = performance.now();
                    (function tick() {
                        const now = performance.now();
                        if (now - lastChange >= 150) {
                            observer.disconnect();
                            return resolve(true);
                        }
                        if (now - start >= 600) {
                            observer.disconnect();
                            return resolve(false);
                        }
                        setTimeout(tick, 50);
                    })();
                })'''
            )

            if not stable:
                # Page still mutating — one short extra wait, then move on.
                self.page.wait_for_timeout(500)

        except Exception as e:
            logger.warning("Page ready wait failed: %s", e)
    
    def get_page_load_status(self) -> Dict[str, Any]:
        """Check page load status"""
        try:
            # Check if page is loaded
            is_loaded = self.page.evaluate('''() => {
                return {
                    readyState: document.readyState,
                    isDOMContentLoaded: document.readyState !== 'loading',
                    isPageComplete: document.readyState === 'complete'
                }
            }''')
            
            return {
                'isResourcesLoading': not is_loaded['isPageComplete'],
                'isDOMContentLoaded': is_loaded['isDOMContentLoaded'],
                'isPageComplete': is_loaded['isPageComplete']
            }
        except Exception as e:
            return {'error': str(e)}
    
    # ========== TAB MANAGEMENT METHODS ==========
    
    def open_new_tab(self, url: Optional[str] = None, purpose: str = None) -> Dict[str, Any]:
        """Open a new tab and optionally navigate to URL. Automatically switches to the new tab."""
        try:
            new_page = self.context.new_page()
            self.pages.append(new_page)
            new_tab_index = len(self.pages) - 1
            
            # Store tab purpose for context
            if purpose:
                self.tab_purposes[new_tab_index] = purpose
            
            result = {
                'success': True,
                'tabIndex': new_tab_index,
                'totalTabs': len(self.pages),
                'purpose': purpose
            }
            
            # Navigate if URL provided
            if url:
                new_page.goto(url, wait_until='domcontentloaded', timeout=30000)
                result['url'] = new_page.url
                result['title'] = new_page.title()
                
                # Track navigation
                self.navigation_history.append({
                    'url': url,
                    'timestamp': time.time(),
                    'tab_index': new_tab_index,
                    'purpose': purpose or 'new_tab'
                })
                self.navigation_history = self.navigation_history[-50:]

            # Automatically switch to the new tab
            self.page = new_page
            self.page.bring_to_front()
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def switch_to_tab(self, tab_index: int) -> Dict[str, Any]:
        """Switch to a specific tab by index"""
        try:
            if tab_index < 0 or tab_index >= len(self.pages):
                return {
                    'success': False, 
                    'error': f'Invalid tab index {tab_index}. Valid range: 0-{len(self.pages) - 1}'
                }
            
            self.current_tab_index = tab_index
            self.page = self.pages[tab_index]
            
            # Bring tab to front
            self.page.bring_to_front()
            
            return {
                'success': True,
                'tabIndex': tab_index,
                'url': self.page.url,
                'title': self.page.title()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close_tab(self, tab_index: Optional[int] = None) -> Dict[str, Any]:
        """Close a specific tab or the current tab"""
        try:
            if len(self.pages) == 1:
                return {'success': False, 'error': 'Cannot close the last tab'}
            
            # Default to current tab if not specified
            if tab_index is None:
                tab_index = self.current_tab_index
            
            if tab_index < 0 or tab_index >= len(self.pages):
                return {
                    'success': False,
                    'error': f'Invalid tab index {tab_index}. Valid range: 0-{len(self.pages) - 1}'
                }
            
            # Close the tab
            self.pages[tab_index].close()
            self.pages.pop(tab_index)
            
            # Adjust current tab index if needed
            if self.current_tab_index >= len(self.pages):
                self.current_tab_index = len(self.pages) - 1
            elif tab_index <= self.current_tab_index and self.current_tab_index > 0:
                self.current_tab_index -= 1
            
            # Update current page reference
            self.page = self.pages[self.current_tab_index]
            self.page.bring_to_front()
            
            return {
                'success': True,
                'closedTabIndex': tab_index,
                'currentTabIndex': self.current_tab_index,
                'remainingTabs': len(self.pages)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_tabs(self) -> Dict[str, Any]:
        """List all open tabs with their details"""
        try:
            tabs = []
            for i, page in enumerate(self.pages):
                tabs.append({
                    'index': i,
                    'url': page.url,
                    'title': page.title(),
                    'isCurrent': i == self.current_tab_index,
                    'purpose': self.tab_purposes.get(i, 'unknown')
                })
            
            return {
                'success': True,
                'tabs': tabs,
                'currentTabIndex': self.current_tab_index,
                'totalTabs': len(self.pages),
                'tabContextSummary': self._get_tab_context_summary()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_tab_context_summary(self) -> str:
        """Generate a summary of current tab context for autonomous decision making"""
        summary_parts = []
        
        # Current tabs overview
        summary_parts.append(f"Total open tabs: {len(self.pages)}")
        
        # Tab purposes
        if self.tab_purposes:
            purposes = [f"Tab {i}: {purpose}" for i, purpose in self.tab_purposes.items()]
            summary_parts.append("Tab purposes: " + ", ".join(purposes))
        
        # Recent navigation patterns
        if len(self.navigation_history) > 0:
            recent = self.navigation_history[-3:]  # Last 3 navigations
            domains = []
            for nav in recent:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(nav['url']).netloc
                    domains.append(domain)
                except:
                    pass
            
            unique_domains = set(domains)
            if len(unique_domains) > 1:
                summary_parts.append(f"Working across {len(unique_domains)} domains: {', '.join(unique_domains)}")
        
        return " | ".join(summary_parts)
    
    def next_tab(self) -> Dict[str, Any]:
        """Switch to the next tab (circular)"""
        next_index = (self.current_tab_index + 1) % len(self.pages)
        return self.switch_to_tab(next_index)
    
    def previous_tab(self) -> Dict[str, Any]:
        """Switch to the previous tab (circular)"""
        prev_index = (self.current_tab_index - 1) % len(self.pages)
        return self.switch_to_tab(prev_index)
    
    def go_back(self) -> Dict[str, Any]:
        """Navigate back in current tab's history"""
        try:
            self.page.go_back(wait_until='domcontentloaded', timeout=30000)
            return {
                'success': True,
                'url': self.page.url,
                'title': self.page.title()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def go_forward(self) -> Dict[str, Any]:
        """Navigate forward in current tab's history"""
        try:
            self.page.go_forward(wait_until='domcontentloaded', timeout=30000)
            return {
                'success': True,
                'url': self.page.url,
                'title': self.page.title()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def reload_tab(self, tab_index: Optional[int] = None) -> Dict[str, Any]:
        """Reload a specific tab or the current tab"""
        try:
            if tab_index is None:
                page_to_reload = self.page
            else:
                if tab_index < 0 or tab_index >= len(self.pages):
                    return {'success': False, 'error': f'Invalid tab index {tab_index}'}
                page_to_reload = self.pages[tab_index]
            
            page_to_reload.reload(wait_until='domcontentloaded', timeout=30000)
            
            return {
                'success': True,
                'url': page_to_reload.url,
                'title': page_to_reload.title()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close_other_tabs(self) -> Dict[str, Any]:
        """Close all tabs except the current one"""
        try:
            current_page = self.page
            
            # Close all other pages
            for i, page in enumerate(self.pages):
                if i != self.current_tab_index:
                    page.close()
            
            # Reset tracking
            self.pages = [current_page]
            self.current_tab_index = 0
            self.page = current_page
            
            return {
                'success': True,
                'remainingTabs': 1
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def duplicate_tab(self, tab_index: Optional[int] = None) -> Dict[str, Any]:
        """Duplicate a tab by opening the same URL in a new tab"""
        try:
            if tab_index is None:
                tab_index = self.current_tab_index
            
            if tab_index < 0 or tab_index >= len(self.pages):
                return {'success': False, 'error': f'Invalid tab index {tab_index}'}
            
            url_to_duplicate = self.pages[tab_index].url
            purpose = self.tab_purposes.get(tab_index, 'unknown')
            return self.open_new_tab(url_to_duplicate, purpose=f"duplicate_{purpose}")
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_navigation_context(self) -> Dict[str, Any]:
        """Get navigation context to help with autonomous tab decisions"""
        try:
            current_url = self.page.url
            current_domain = ''
            try:
                from urllib.parse import urlparse
                current_domain = urlparse(current_url).netloc
            except:
                pass
            
            # Analyze if we're about to navigate to a different domain
            recent_domains = []
            for nav in self.navigation_history[-5:]:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(nav['url']).netloc
                    recent_domains.append(domain)
                except:
                    pass
            
            unique_recent_domains = list(set(recent_domains))
            
            return {
                'success': True,
                'currentUrl': current_url,
                'currentDomain': current_domain,
                'totalTabs': len(self.pages),
                'currentTabIndex': self.current_tab_index,
                'recentDomains': unique_recent_domains,
                'workingAcrossMultipleDomains': len(unique_recent_domains) > 1,
                'tabPurposes': self.tab_purposes,
                'recommendation': self._get_tab_recommendation(current_domain, unique_recent_domains)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_tab_recommendation(self, current_domain: str, recent_domains: List[str]) -> str:
        """Provide recommendation on whether to use a new tab"""
        # If working across multiple domains, suggest new tabs
        if len(recent_domains) > 2:
            return "Consider using new tabs when switching between different domains or tasks"
        
        # If only one tab and switching domains
        if len(self.pages) == 1 and len(recent_domains) > 1:
            return "Opening a new tab might help organize work across different sites"
        
        return "Current tab organization seems appropriate"
