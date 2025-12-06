"""
Browser Controller - Handles all browser automation using Playwright
"""
from playwright.sync_api import sync_playwright, Page, Browser, Playwright
from typing import Dict, List, Any, Optional
import base64
import time


class BrowserController:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.snapshot_cache: Dict[str, Any] = {}
        
    def start(self):
        """Initialize browser"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--start-maximized']
        )
        context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = context.new_page()
        print("✓ Browser started")
        
    def close(self):
        """Close browser"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("✓ Browser closed")
        
    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL with smart waiting"""
        try:
            # Navigate - use 'domcontentloaded' instead of 'networkidle' for faster/more reliable navigation
            # 'networkidle' can timeout on sites like YouTube that constantly make requests
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for body to be visible
            try:
                self.page.wait_for_selector('body', state='visible', timeout=10000)
            except:
                pass  # Some pages may not have body immediately visible
            
            # Small delay for initial rendering
            self.page.wait_for_timeout(500)
            
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
        Replicates browserOS.getInteractiveSnapshot
        """
        try:
            # Wait for page to be ready
            self._wait_for_page_ready()
            
            # Get accessibility tree with retry logic
            snapshot = self._get_accessibility_snapshot_with_retry()
            
            interactive_elements = []
            node_id = 0
            
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
                typeable_roles = ['textbox', 'searchbox', 'combobox']
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
                        interactive_elements.append(element_info)
                        node_id += 1
                
                # Recurse through children
                for child in node.get('children', []):
                    extract_interactive(child, depth + 1)
            
            if snapshot:
                extract_interactive(snapshot)
            
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
    
    def _is_in_viewport(self, rect: Dict) -> bool:
        """Check if element is in viewport"""
        viewport = self.page.viewport_size
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
    
    def click(self, node_id: int) -> Dict[str, bool]:
        """Click on element by nodeId"""
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
                except:
                    pass
            
            # Strategy 2: Click by coordinates
            if not clicked and element['rect']:
                try:
                    x = element['rect']['x'] + element['rect']['width'] / 2
                    y = element['rect']['y'] + element['rect']['height'] / 2
                    self.page.mouse.click(x, y)
                    clicked = True
                except:
                    pass
            
            # Strategy 3: Click by text
            if not clicked and element['name']:
                try:
                    self.page.get_by_text(element['name'], exact=False).first.click(timeout=5000)
                    clicked = True
                except:
                    pass
            
            # Smart wait after click - wait for navigation or network idle
            if clicked:
                try:
                    # Wait for either navigation or network to settle (whichever comes first)
                    self.page.wait_for_load_state('domcontentloaded', timeout=3000)
                except:
                    # If no navigation, just wait briefly for any changes
                    self.page.wait_for_timeout(500)
            
            return {'success': clicked}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def input_text(self, node_id: int, text: str) -> Dict[str, bool]:
        """Input text into element"""
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
                    self.page.keyboard.type(text)
                    filled = True
                except:
                    pass
            
            # Wait for any input event handlers to process
            if filled:
                self.page.wait_for_timeout(300)
            
            return {'success': filled}
            
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
