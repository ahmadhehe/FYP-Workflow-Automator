"""
Browser Agent - Main orchestration logic
"""
from browser_controller import BrowserController
from llm_client import LLMClient
from typing import Dict, Any, List
import json
import os
from dotenv import load_dotenv

load_dotenv()


class BrowserAgent:
    def __init__(self, provider: str = None, headless: bool = False, use_profile: bool = True, google_sheets_client=None):
        """Initialize the browser agent"""
        provider = provider or os.getenv("DEFAULT_PROVIDER", "openai")
        
        self.provider = provider  # Track current provider
        self.browser = BrowserController(headless=headless, use_profile=use_profile)
        self.llm = LLMClient(provider=provider)
        self.google_sheets = google_sheets_client  # Optional Google Sheets client
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_iterations = 45
        
        # Token tracking for current workflow
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
        print(f"✓ Agent initialized with {provider}")
    
    def set_provider(self, provider: str):
        """Change the LLM provider"""
        if provider != self.provider:
            print(f"✓ Switching provider from {self.provider} to {provider}")
            self.provider = provider
            self.llm = LLMClient(provider=provider)
    
    def reset_token_tracking(self):
        """Reset token counters for a new workflow"""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get current token usage"""
        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'total_tokens': self.total_input_tokens + self.total_output_tokens
        }
    
    def start(self):
        """Start the browser"""
        self.browser.start()
    
    def close(self):
        """Close the browser"""
        self.browser.close()
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool call from the LLM"""
        print(f"  🔧 Executing: {tool_name}({arguments})")
        
        try:
            if tool_name == 'getInteractiveSnapshot':
                viewport_only = arguments.get('viewportOnly', True)
                result = self.browser.get_interactive_snapshot(viewport_only)
                # Truncate for display
                display_result = {
                    'elements': f"{len(result.get('elements', []))} elements found",
                    'sample': result.get('elements', [])[:3]
                }
                print(f"    ✓ Found {len(result.get('elements', []))} interactive elements")
                return result
                
            elif tool_name == 'click':
                node_id = int(arguments['nodeId'])  # Convert float to int
                result = self.browser.click(node_id)
                print(f"    ✓ Click {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'clickByText':
                element_type = arguments.get('elementType', 'any')
                result = self.browser.click_by_text(arguments['text'], element_type)
                print(f"    ✓ Click by text '{arguments['text']}' {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'checkFormErrors':
                result = self.browser.check_for_form_errors()
                if result.get('hasErrors'):
                    print(f"    ⚠️  Form errors found: {result.get('errors', [])}")
                else:
                    print(f"    ✓ No form errors detected")
                return result
                
            elif tool_name == 'inputText':
                node_id = int(arguments['nodeId'])  # Convert float to int
                result = self.browser.input_text(node_id, arguments['text'])
                print(f"    ✓ Input text {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'selectDate':
                node_id = int(arguments['nodeId'])  # Convert float to int
                result = self.browser.select_date(node_id, arguments['date'])
                print(f"    ✓ Date selection {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'getElementState':
                node_id = int(arguments['nodeId'])  # Convert float to int
                result = self.browser.get_element_state(node_id)
                print(f"    ✓ Got element state")
                return result
            
            elif tool_name == 'selectDropdownOption':
                node_id = int(arguments['nodeId'])  # Convert float to int
                result = self.browser.select_dropdown_option(node_id, arguments['optionText'])
                print(f"    ✓ Dropdown selection {'succeeded' if result.get('success') else 'failed'}")
                return result
                
            elif tool_name == 'navigate':
                result = self.browser.navigate(arguments['url'])
                print(f"    ✓ Navigated to {result.get('url', 'unknown')}")
                return result
                
            elif tool_name == 'scrollDown':
                result = self.browser.scroll_down()
                print(f"    ✓ Scrolled down")
                return result
                
            elif tool_name == 'scrollUp':
                result = self.browser.scroll_up()
                print(f"    ✓ Scrolled up")
                return result
                
            elif tool_name == 'getPageContent':
                result = self.browser.get_page_content()
                print(f"    ✓ Retrieved page content ({len(result.get('content', ''))} chars)")
                return result
                
            elif tool_name == 'captureScreenshot':
                full_page = arguments.get('fullPage', False)
                result = self.browser.capture_screenshot(full_page)
                print(f"    ✓ Screenshot captured")
                return {'success': True, 'message': 'Screenshot captured (base64 data omitted for brevity)'}
                
            elif tool_name == 'sendKeys':
                result = self.browser.send_keys(arguments['key'])
                print(f"    ✓ Sent key: {arguments['key']}")
                return result
                
            elif tool_name == 'getPageLoadStatus':
                result = self.browser.get_page_load_status()
                print(f"    ✓ Page load status checked")
                return result
            
            # Tab Management Tools
            elif tool_name == 'openNewTab':
                url = arguments.get('url')
                purpose = arguments.get('purpose')
                result = self.browser.open_new_tab(url, purpose)
                purpose_str = f" for '{purpose}'" if purpose else ""
                print(f"    ✓ Opened new tab (index {result.get('tabIndex')}){purpose_str}")
                return result
                
            elif tool_name == 'switchToTab':
                tab_idx = int(arguments['tabIndex'])  # Convert float to int
                result = self.browser.switch_to_tab(tab_idx)
                print(f"    ✓ Switched to tab {tab_idx}")
                return result
                
            elif tool_name == 'closeTab':
                tab_index = arguments.get('tabIndex')
                if tab_index is not None:
                    tab_index = int(tab_index)  # Convert float to int
                result = self.browser.close_tab(tab_index)
                print(f"    ✓ Closed tab")
                return result
                
            elif tool_name == 'listTabs':
                result = self.browser.list_tabs()
                print(f"    ✓ Listed {result.get('totalTabs', 0)} tabs")
                return result
                
            elif tool_name == 'nextTab':
                result = self.browser.next_tab()
                print(f"    ✓ Switched to next tab")
                return result
                
            elif tool_name == 'previousTab':
                result = self.browser.previous_tab()
                print(f"    ✓ Switched to previous tab")
                return result
                
            elif tool_name == 'goBack':
                result = self.browser.go_back()
                print(f"    ✓ Navigated back")
                return result
                
            elif tool_name == 'goForward':
                result = self.browser.go_forward()
                print(f"    ✓ Navigated forward")
                return result
                
            elif tool_name == 'reloadTab':
                tab_index = arguments.get('tabIndex')
                result = self.browser.reload_tab(tab_index)
                print(f"    ✓ Reloaded tab")
                return result
                
            elif tool_name == 'closeOtherTabs':
                result = self.browser.close_other_tabs()
                print(f"    ✓ Closed other tabs")
                return result
                
            elif tool_name == 'duplicateTab':
                tab_index = arguments.get('tabIndex')
                result = self.browser.duplicate_tab(tab_index)
                print(f"    ✓ Duplicated tab")
                return result
            
            elif tool_name == 'getNavigationContext':
                result = self.browser.get_navigation_context()
                print(f"    ✓ Retrieved navigation context")
                return result
            
            # Google Sheets API Tools
            elif tool_name == 'readSpreadsheet':
                if not self.google_sheets or not self.google_sheets.is_authenticated():
                    return {'success': False, 'error': 'Google account not connected. Please ask the user to connect their Google account in Settings.'}
                result = self.google_sheets.read_spreadsheet(
                    arguments['spreadsheetId'],
                    arguments['range']
                )
                print(f"    ✓ Read spreadsheet {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'writeSpreadsheet':
                if not self.google_sheets or not self.google_sheets.is_authenticated():
                    return {'success': False, 'error': 'Google account not connected. Please ask the user to connect their Google account in Settings.'}
                values = arguments['values']
                if isinstance(values, str):
                    values = json.loads(values)
                result = self.google_sheets.write_spreadsheet(
                    arguments['spreadsheetId'],
                    arguments['range'],
                    values
                )
                print(f"    ✓ Write spreadsheet {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'appendRows':
                if not self.google_sheets or not self.google_sheets.is_authenticated():
                    return {'success': False, 'error': 'Google account not connected. Please ask the user to connect their Google account in Settings.'}
                values = arguments['values']
                if isinstance(values, str):
                    values = json.loads(values)
                result = self.google_sheets.append_rows(
                    arguments['spreadsheetId'],
                    arguments['range'],
                    values
                )
                print(f"    ✓ Append rows {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'createSpreadsheet':
                if not self.google_sheets or not self.google_sheets.is_authenticated():
                    return {'success': False, 'error': 'Google account not connected. Please ask the user to connect their Google account in Settings.'}
                result = self.google_sheets.create_spreadsheet(
                    arguments['title'],
                    arguments.get('sheetNames')
                )
                print(f"    ✓ Create spreadsheet {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'getSheetsList':
                if not self.google_sheets or not self.google_sheets.is_authenticated():
                    return {'success': False, 'error': 'Google account not connected. Please ask the user to connect their Google account in Settings.'}
                result = self.google_sheets.get_sheets_list(
                    arguments['spreadsheetId']
                )
                print(f"    ✓ Get sheets list {'succeeded' if result.get('success') else 'failed'}")
                return result
            
            elif tool_name == 'formatCells':
                if not self.google_sheets or not self.google_sheets.is_authenticated():
                    return {'success': False, 'error': 'Google account not connected. Please ask the user to connect their Google account in Settings.'}
                requests_data = arguments['requests']
                if isinstance(requests_data, str):
                    requests_data = json.loads(requests_data)
                result = self.google_sheets.format_cells(
                    arguments['spreadsheetId'],
                    requests_data
                )
                print(f"    ✓ Format cells {'succeeded' if result.get('success') else 'failed'}")
                return result
                
            else:
                error = f"Unknown tool: {tool_name}"
                print(f"    ✗ {error}")
                return {'error': error}
                
        except Exception as e:
            error = str(e)
            print(f"    ✗ Error: {error}")
            return {'error': error}
    
    def run(self, user_instruction: str, initial_url: str = None, file_context: str = None) -> str:
        """
        Run the agent with a user instruction
        
        Args:
            user_instruction: What the user wants to accomplish
            initial_url: Optional starting URL
            file_context: Optional file content to provide as context
            
        Returns:
            Final response from the agent
        """
        print(f"\n{'='*60}")
        print(f"🎯 Task: {user_instruction}")
        print(f"{'='*60}\n")
        
        # Navigate to initial URL if provided
        if initial_url:
            print(f"🌐 Navigating to {initial_url}")
            self.browser.navigate(initial_url)
        
        # Build user message with optional file context
        user_message = user_instruction
        if file_context:
            user_message = f"{user_instruction}\n\n[File Context Provided by User:]\n{file_context}"
            print(f"📄 File context included in prompt")
        
        # Initialize conversation with system prompt and user message
        self.conversation_history = [
            {'role': 'system', 'content': self.llm.get_system_prompt()},
            {'role': 'user', 'content': user_message}
        ]
        
        tools = self.llm.get_tools_definition()
        
        # Loop detection: track recent tool calls
        recent_tools = []
        
        for iteration in range(self.max_iterations):
            print(f"\n--- Iteration {iteration + 1}/{self.max_iterations} ---")
            
            # Call LLM
            try:
                response = self.llm.chat_completion(
                    messages=self.conversation_history,
                    tools=tools,
                    tool_choice='auto'
                )
            except Exception as e:
                print(f"✗ LLM Error: {e}")
                return f"Error: {e}"
            
            # Check if LLM wants to finish
            if response.content and not response.tool_calls:
                print(f"\n✅ Agent: {response.content}")
                self.conversation_history.append({
                    'role': 'assistant',
                    'content': response.content
                })
                return response.content
            
            # Execute tool calls
            if response.tool_calls:
                # Add assistant message with tool calls
                tool_calls_data = []
                for tc in response.tool_calls:
                    tool_calls_data.append({
                        'id': tc.id,
                        'type': 'function',
                        'function': {
                            'name': tc.function.name,
                            'arguments': tc.function.arguments
                        }
                    })
                
                self.conversation_history.append({
                    'role': 'assistant',
                    'content': response.content,
                    'tool_calls': tool_calls_data
                })
                
                # Execute each tool call
                for tool_call in response.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    # Loop detection: check if calling same tool repeatedly
                    recent_tools.append(function_name)
                    if len(recent_tools) > 5:
                        recent_tools.pop(0)
                    
                    # If same tool called 3+ times in a row, inject a hint
                    if len(recent_tools) >= 3 and len(set(recent_tools[-3:])) == 1:
                        repeated_tool = recent_tools[-1]
                        print(f"    ⚠️  Loop detected: {repeated_tool} called 3 times in a row")
                        
                        # Add a hint message to break the loop
                        hint = f"LOOP DETECTED: You called {repeated_tool} multiple times without taking action. "
                        if repeated_tool == 'getInteractiveSnapshot':
                            hint += "STOP getting snapshots! Look at the form fields in the snapshot you already have and use inputText(nodeId, text) to fill them, or use click(nodeId) to click checkboxes/radios, or use clickByText('Next') if you see a Next button. DO NOT call getInteractiveSnapshot again!"
                        else:
                            hint += "Try a DIFFERENT approach or tool."
                        
                        self.conversation_history.append({
                            'role': 'user',
                            'content': hint
                        })
                    
                    # Execute tool
                    result = self.execute_tool(function_name, arguments)
                    
                    # Add tool result to conversation
                    self.conversation_history.append({
                        'role': 'tool',
                        'tool_call_id': tool_call.id,
                        'content': json.dumps(result, default=str)
                    })
        
        # Max iterations reached
        final_message = "Task incomplete - reached maximum iterations. Please try breaking down the task into smaller steps."
        print(f"\n⚠️  {final_message}")
        return final_message


def main():
    """Example usage"""
    import sys
    
    # Create agent
    agent = BrowserAgent(headless=False)
    
    try:
        # Start browser
        agent.start()
        
        # Example tasks - uncomment the one you want to try
        
        # Task 1: Simple navigation and extraction
        # agent.run(
        #     "Go to example.com and tell me what the main heading says",
        #     initial_url="https://example.com"
        # )
        
        # Task 2: Search on Google
        # agent.run(
        #     "Search for 'playwright automation' on Google and tell me the first result",
        #     initial_url="https://google.com"
        # )
        
        # Task 3: Fill a form (you'll need a test site with a form)
        agent.run(
            "go to lms.iba.edu.pk, and download assignment 3 for intro to machine learning, with the username 24478 and pass Abc@4478",
            initial_url="https://www.google.com"
        )
        
    finally:
        # Always close browser
        agent.close()


if __name__ == "__main__":
    main()
