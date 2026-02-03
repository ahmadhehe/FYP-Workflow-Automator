"""
Browser Controller - Handles all browser automation using Playwright
"""
from playwright.sync_api import sync_playwright, Page, Browser, Playwright, BrowserContext
from typing import Dict, List, Any, Optional
import base64
import time
import os

# Default profile directory for persistent browser data
DEFAULT_PROFILE_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")


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
            except:
                pass  # Some pages may not have body immediately visible
            
            # Give additional time for JavaScript to initialize
            self.page.wait_for_timeout(1000)
            
            # Wait for any pending navigation
            try:
                self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            except:
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
        Get snapshot of interactive elements on the page
        Uses both accessibility tree AND DOM queries for better coverage
        """
        try:
            # Wait for page to be ready
            self._wait_for_page_ready()
            
            # Get accessibility tree with retry logic
            snapshot = self._get_accessibility_snapshot_with_retry()
            
            interactive_elements = []
            node_id = 0
            seen_elements = set()  # Track elements to avoid duplicates
            
            def extract_interactive(node: Dict, depth: int = 0):
                nonlocal node_id
                
                role = node.get('role', '')
                name = node.get('name', '')
                value = node.get('value', '')
                
                # Determine if element is interactive
                clickable_roles = [
                    'button', 'link', 'checkbox', 'radio', 'menuitem', 
                    'tab', 'switch', 'option', 'treeitem'
                ]
                typeable_roles = ['textbox', 'searchbox', 'combobox', 'spinbutton']
                selectable_roles = ['listbox', 'combobox', 'menu']
                
                is_clickable = role in clickable_roles
                is_typeable = role in typeable_roles
                is_selectable = role in selectable_roles
                
                if is_clickable or is_typeable or is_selectable:
                    element_type = (
                        'clickable' if is_clickable 
                        else 'typeable' if is_typeable 
                        else 'selectable'
                    )
                    
                    # Try to get bounding box
                    rect = None
                    try:
                        if name:
                            # Try to locate element
                            locators = [
                                self.page.get_by_role(role, name=name, exact=False),
                                self.page.get_by_text(name, exact=False),
                                self.page.get_by_label(name, exact=False)
                            ]
                            
                            for locator in locators:
                                try:
                                    if locator.count() > 0:
                                        rect = locator.first.bounding_box(timeout=1000)
                                        if rect:
                                            break
                                except:
                                    continue
                    except:
                        pass
                    
                    element_info = {
                        'nodeId': node_id,
                        'type': element_type,
                        'name': name,
                        'role': role,
                        'rect': rect,
                        'attributes': {
                            'value': value,
                            'description': node.get('description', ''),
                            'depth': depth
                        }
                    }
                    
                    # Filter by viewport if requested
                    if not viewport_only or (rect and self._is_in_viewport(rect)):
                        # Create a key to track this element
                        elem_key = f"{role}:{name}:{rect}" if rect else f"{role}:{name}"
                        if elem_key not in seen_elements:
                            seen_elements.add(elem_key)
                            interactive_elements.append(element_info)
                            node_id += 1
                
                # Recurse through children
                for child in node.get('children', []):
                    extract_interactive(child, depth + 1)
            
            if snapshot:
                extract_interactive(snapshot)
            
            # ALSO query DOM directly for form inputs that accessibility tree might miss
            # This is crucial for Google Forms and other custom form implementations
            dom_inputs = self._get_dom_form_elements()
            for dom_elem in dom_inputs:
                elem_key = f"{dom_elem['role']}:{dom_elem['name']}:{dom_elem.get('rect')}"
                if elem_key not in seen_elements:
                    dom_elem['nodeId'] = node_id
                    interactive_elements.append(dom_elem)
                    seen_elements.add(elem_key)
                    node_id += 1
            
            # Generate hierarchical structure for context
            hierarchical = self._build_hierarchy(interactive_elements)
            
            result = {
                'snapshotId': int(time.time() * 1000),
                'timestamp': time.time(),
                'elements': interactive_elements,
                'hierarchicalStructure': hierarchical,
                'processingTimeMs': 0
            }
            
            # Cache for later use
            self.snapshot_cache['latest'] = result
            
            return result
            
        except Exception as e:
            return {
                'error': str(e),
                'elements': []
            }
    
    def _get_dom_form_elements(self) -> List[Dict]:
        """
        Query DOM directly for form elements that accessibility tree might miss.
        Essential for Google Forms and other custom form implementations.
        """
        try:
            # JavaScript to find form inputs - much more comprehensive for Google Forms
            form_elements = self.page.evaluate('''() => {
                const results = [];
                const seenRects = new Set();
                
                function addElement(el, labelOverride = null) {
                    const rect = el.getBoundingClientRect();
                    // Skip invisible or too small elements
                    if (rect.width < 10 || rect.height < 10) return;
                    
                    // Skip if we've already seen this position
                    const rectKey = `${Math.round(rect.x)},${Math.round(rect.y)}`;
                    if (seenRects.has(rectKey)) return;
                    seenRects.add(rectKey);
                    
                    const type = el.type || el.getAttribute('data-type') || el.tagName.toLowerCase();
                    
                    // Try multiple ways to get the label/name
                    let name = labelOverride ||
                               el.getAttribute('aria-label') || 
                               el.getAttribute('placeholder') ||
                               el.getAttribute('data-placeholder') ||
                               el.getAttribute('name') ||
                               el.getAttribute('data-params')?.match(/"([^"]+)"/)?.[1] ||
                               '';
                    
                    // Try to find label from parent structure (Google Forms)
                    if (!name) {
                        const parent = el.closest('[role="listitem"], [data-params]');
                        if (parent) {
                            const heading = parent.querySelector('[role="heading"]');
                            if (heading) name = heading.textContent?.trim() || '';
                        }
                    }
                    
                    // Try nearby label
                    if (!name) {
                        const closestLabel = el.closest('label');
                        if (closestLabel) name = closestLabel.textContent?.trim() || '';
                    }
                    
                    results.push({
                        tagName: el.tagName.toLowerCase(),
                        type: type,
                        name: (name || 'unnamed').substring(0, 100),
                        value: el.value || el.textContent?.substring(0, 50) || '',
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        isDate: type === 'date' || 
                                name.toLowerCase().includes('date') || 
                                name.toLowerCase().includes('birth') ||
                                name.toLowerCase().includes('dob'),
                        checked: el.checked || el.getAttribute('aria-checked') === 'true',
                        role: el.getAttribute('role') || ''
                    });
                }
                
                // 1. Standard form elements
                document.querySelectorAll('input, textarea, select').forEach(el => addElement(el));
                
                // 2. Contenteditable elements (often used for text input)
                document.querySelectorAll('[contenteditable="true"]').forEach(el => addElement(el));
                
                // 3. Elements with specific ARIA roles (critical for Google Forms)
                document.querySelectorAll('[role="textbox"], [role="combobox"], [role="listbox"], [role="option"], [role="radio"], [role="checkbox"]').forEach(el => addElement(el));
                
                // 4. Google Forms specific: data-value inputs
                document.querySelectorAll('[data-value], [data-answer-value]').forEach(el => addElement(el));
                
                // 5. Google Forms question containers - find clickable areas
                document.querySelectorAll('[role="listitem"]').forEach(container => {
                    // Get the question label
                    const heading = container.querySelector('[role="heading"]');
                    const label = heading?.textContent?.trim() || '';
                    
                    // Find all interactive elements within
                    container.querySelectorAll('input, textarea, [role="textbox"], [role="listbox"], [role="combobox"], [data-value]').forEach(el => {
                        addElement(el, label);
                    });
                    
                    // For radio/checkbox groups, find the options
                    container.querySelectorAll('[role="radio"], [role="checkbox"], [data-answer-value]').forEach(el => {
                        const optionLabel = el.getAttribute('data-value') || el.getAttribute('aria-label') || el.textContent?.trim() || '';
                        addElement(el, label + ': ' + optionLabel);
                    });
                });
                
                // 6. Clickable divs that look like buttons or dropdowns
                document.querySelectorAll('[role="button"], [role="menuitem"], [tabindex="0"]').forEach(el => {
                    const text = el.textContent?.trim() || '';
                    // Skip navigation elements
                    if (!text.match(/^(Next|Back|Submit|Previous|Clear|Cancel|Close)/i)) return;
                    addElement(el, text);
                });
                
                return results;
            }''')
            
            # Convert to our element format
            result_elements = []
            for elem in form_elements:
                # Determine role
                if elem['type'] == 'checkbox':
                    role = 'checkbox'
                    elem_type = 'clickable'
                elif elem['type'] == 'radio':
                    role = 'radio'
                    elem_type = 'clickable'
                elif elem['type'] == 'date' or elem.get('isDate'):
                    role = 'textbox'  # Date inputs
                    elem_type = 'date-input'
                elif elem['tagName'] == 'select':
                    role = 'combobox'
                    elem_type = 'selectable'
                else:
                    role = 'textbox'
                    elem_type = 'typeable'
                
                result_elements.append({
                    'type': elem_type,
                    'name': elem['name'],
                    'role': role,
                    'rect': elem['rect'],
                    'attributes': {
                        'value': elem.get('value', ''),
                        'description': f"DOM element: {elem['tagName']}",
                        'depth': 0,
                        'isDate': elem.get('isDate', False),
                        'tagName': elem['tagName'],
                        'inputType': elem['type']
                    }
                })
            
            return result_elements
            
        except Exception as e:
            print(f"Error getting DOM form elements: {e}")
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
            # Wait a bit for any animations to complete
            self.page.wait_for_timeout(300)
            
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available'}
            
            # Find element
            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {'success': False, 'error': f'Element {node_id} not found'}
            
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
            
            # Try different click strategies
            clicked = False
            
            # Strategy 1: Click by role and name
            if element['name']:
                try:
                    locator = self.page.get_by_role(element['role'], name=element['name'], exact=False)
                    if locator.count() > 0:
                        # Wait for element to be stable before clicking
                        locator.first.wait_for(state='visible', timeout=5000)
                        locator.first.click(timeout=5000)
                        clicked = True
                except Exception as e:
                    print(f"    Strategy 1 failed: {e}")
            
            # Strategy 2: Click by coordinates
            if not clicked and element['rect']:
                try:
                    x = element['rect']['x'] + element['rect']['width'] / 2
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    self.page.mouse.click(x, y)
                    clicked = True
                except Exception as e:
                    print(f"    Strategy 2 failed: {e}")
            
            # Strategy 3: Click by text
            if not clicked and element['name']:
                try:
                    self.page.get_by_text(element['name'], exact=False).first.click(timeout=5000)
                    clicked = True
                except Exception as e:
                    print(f"    Strategy 3 failed: {e}")
            
            # Smart wait after click - wait for navigation or network idle
            if clicked:
                try:
                    # Wait for either navigation or network to settle (whichever comes first)
                    self.page.wait_for_load_state('domcontentloaded', timeout=3000)
                except:
                    # If no navigation, just wait briefly for any changes
                    self.page.wait_for_timeout(500)
                
                # Verify state changed if applicable
                post_state = None
                if verify_action and element['role'] in ['checkbox', 'radio', 'switch'] and pre_state:
                    post_state = self.get_element_state(node_id)
            
            result = {'success': clicked}
            if pre_state:
                result['pre_state'] = pre_state
            if 'post_state' in locals() and post_state:
                result['post_state'] = post_state
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def input_text(self, node_id: int, text: str) -> Dict[str, bool]:
        """Input text into element with verification"""
        try:
            # Wait for any animations
            self.page.wait_for_timeout(300)
            
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available'}
            
            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {'success': False, 'error': f'Element {node_id} not found'}
            
            # Try to find and fill the input
            filled = False
            
            # Strategy 1: By role and name
            if element['name']:
                try:
                    locator = self.page.get_by_role(element['role'], name=element['name'], exact=False)
                    if locator.count() > 0:
                        # Wait for element to be ready
                        locator.first.wait_for(state='visible', timeout=5000)
                        locator.first.fill(text)
                        filled = True
                except:
                    pass
            
            # Strategy 2: By label
            if not filled and element['name']:
                try:
                    self.page.get_by_label(element['name'], exact=False).first.fill(text)
                    filled = True
                except:
                    pass
            
            # Strategy 3: Click at coordinates then type
            if not filled and element['rect']:
                try:
                    x = element['rect']['x'] + element['rect']['width'] / 2
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    self.page.mouse.click(x, y)
                    time.sleep(0.2)
                    # Clear existing text first
                    self.page.keyboard.press('Control+A')
                    time.sleep(0.1)
                    self.page.keyboard.type(text)
                    filled = True
                except:
                    pass
            
            # Wait for any input event handlers to process
            if filled:
                self.page.wait_for_timeout(300)
                
                # VERIFY the text was actually entered
                try:
                    if element['rect']:
                        verify_result = self.page.evaluate(f'''() => {{
                            const inputs = document.querySelectorAll('input, textarea, [contenteditable="true"]');
                            for (const input of inputs) {{
                                const rect = input.getBoundingClientRect();
                                if (Math.abs(rect.x - {element['rect']['x']}) < 20 && 
                                    Math.abs(rect.y - {element['rect']['y']}) < 20) {{
                                    const value = input.value || input.textContent || '';
                                    return {{ value: value, hasValue: value.length > 0 }};
                                }}
                            }}
                            return {{ value: '', hasValue: false }};
                        }}''')
                        
                        if not verify_result.get('hasValue'):
                            print(f"    ⚠️  Text verification failed - value may not be set")
                            # Don't fail completely, but warn
                except Exception as verify_err:
                    print(f"    Verification check error: {verify_err}")
            
            return {'success': filled}
            
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
    
    def click_by_text(self, text: str, element_type: str = 'any') -> Dict[str, Any]:
        """
        Click on an element by its visible text content.
        More reliable than nodeId for buttons like "Next", "Submit", etc.
        
        Args:
            text: The visible text to click (e.g., "Next", "Submit", "Sign in")
            element_type: Type of element - 'button', 'link', or 'any'
        """
        try:
            self.page.wait_for_timeout(300)
            
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
            
            # Wait for page to respond
            if clicked:
                try:
                    self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                except:
                    pass
                self.page.wait_for_timeout(500)
            
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
                return {'success': False, 'error': 'No snapshot available'}
            
            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {'success': False, 'error': f'Element {node_id} not found'}
            
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
    
    def _select_dropdown_by_coord(self, rect: Dict, value: str):
        """Helper to select a dropdown value by clicking coordinates"""
        x = rect['x'] + rect['width'] / 2
        y = rect['y'] + rect['height'] / 2
        
        # Open dropdown
        self.page.mouse.click(x, y)
        self.page.wait_for_timeout(300)
        
        # Try to click the option with the value
        try:
            self.page.get_by_role('option', name=value).first.click(timeout=2000)
        except:
            # Type to filter and press Enter
            self.page.keyboard.type(value)
            self.page.wait_for_timeout(200)
            self.page.keyboard.press('Enter')
        
        self.page.wait_for_timeout(200)
    
    def get_element_state(self, node_id: int) -> Dict[str, Any]:
        """
        Get the current state of an element (checked, selected, value, etc.)
        Useful to avoid double-toggling checkboxes/radios
        """
        try:
            snapshot = self.snapshot_cache.get('latest')
            if not snapshot:
                return {'success': False, 'error': 'No snapshot available'}
            
            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {'success': False, 'error': f'Element {node_id} not found'}
            
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
                return {'success': False, 'error': 'No snapshot available'}
            
            element = next((e for e in snapshot['elements'] if e['nodeId'] == node_id), None)
            if not element:
                return {'success': False, 'error': f'Element {node_id} not found'}
            
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
            time.sleep(0.3)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def scroll_up(self) -> Dict[str, bool]:
        """Scroll up by viewport height"""
        try:
            self.page.evaluate('window.scrollBy(0, -window.innerHeight * 0.8)')
            time.sleep(0.3)
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
        """Smart wait for page to be ready for interaction"""
        try:
            # Wait for network to be mostly idle
            self.page.wait_for_load_state('domcontentloaded', timeout=timeout)
            
            # Wait for body to exist
            self.page.wait_for_selector('body', timeout=5000)
            
            # Check if page has stabilized (no major DOM changes)
            stable = self.page.evaluate('''
                () => {
                    return new Promise((resolve) => {
                        let changeCount = 0;
                        const observer = new MutationObserver(() => {
                            changeCount++;
                        });
                        
                        observer.observe(document.body, {
                            childList: true,
                            subtree: true
                        });
                        
                        // Wait 2 seconds and check if changes are minimal
                        setTimeout(() => {
                            observer.disconnect();
                            resolve(changeCount < 50); // Arbitrary threshold
                        }, 2000);
                    });
                }
            ''')
            
            if not stable:
                # Page is still changing rapidly, wait a bit more
                self.page.wait_for_timeout(2000)
                
        except Exception as e:
            # If waiting fails, continue anyway
            print(f"Warning: Page ready wait failed: {e}")
    
    def _get_accessibility_snapshot_with_retry(self, max_retries: int = 3):
        """Get accessibility snapshot with exponential backoff retry"""
        for attempt in range(max_retries):
            try:
                snapshot = self.page.accessibility.snapshot()
                if snapshot:
                    return snapshot
                    
                # If empty, wait and retry
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 1000  # 1s, 2s, 3s
                    self.page.wait_for_timeout(wait_time)
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                # Exponential backoff
                wait_time = (2 ** attempt) * 1000
                self.page.wait_for_timeout(wait_time)
        
        return None
    
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
