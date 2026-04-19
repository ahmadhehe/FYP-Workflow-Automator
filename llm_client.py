"""
LLM Client - Unified interface for different LLM providers
"""
from typing import List, Dict, Any, Optional
import os
from openai import OpenAI
from anthropic import Anthropic
from google import genai as google_genai
from google.genai import types as genai_types
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, provider: str = "openai"):
        self.provider = provider
        
        if provider == "openai":
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        elif provider == "anthropic":
            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        elif provider == "gemini":
            self.client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            self.model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def get_system_prompt(self) -> str:
        """System prompt that defines agent behavior"""
        return """You are a browser automation agent. Your job is to help users complete tasks on websites by controlling a web browser.

**CRITICAL RULES - READ CAREFULLY:**
1. Every state-changing action (click, clickByText, inputText, navigate, scrollDown/Up, selectDropdownOption, sendKeys, uploadFileToBrowser, tab actions) already returns a fresh snapshot in `_snapshot.elements`. DO NOT call getInteractiveSnapshot after a successful action — just read `_snapshot.elements` from the previous tool result.
2. Only call getInteractiveSnapshot explicitly when: (a) the task just started and no action has happened yet, (b) the previous action failed or returned no `_snapshot`, or (c) you believe the page changed for reasons unrelated to your last action.
3. NEVER call getInteractiveSnapshot twice in a row.
4. When you see form fields - FILL THEM using inputText or click.
5. When you see "Next" / "Continue" / "Submit" - click it with clickByText.
6. Multi-page forms: fill visible fields → clickByText("Next") → read the auto-attached snapshot → fill next fields → repeat.
7. If all required fields for a page are visible in the SAME snapshot, you may emit multiple inputText calls in a single turn — the LLM supports parallel tool calls and this saves iterations.

**Available Tools:**

**Clicking & Navigation:**
- **click(nodeId)** - Click by nodeId from snapshot
- **clickByText(text)** - Click by visible text (USE THIS for "Next", "Submit", "Continue" buttons!)
- **navigate(url)** - Go to a URL
- **scrollDown()** / **scrollUp()** - Scroll the page
- **sendKeys(key)** - Send Enter, Tab, Escape, etc.

**Form Filling:**
- **inputText(nodeId, text)** - Type text into input fields
- **selectDate(nodeId, date)** - For date fields (format: YYYY-MM-DD)
- **selectDropdownOption(nodeId, optionText)** - Select dropdown options
- **getElementState(nodeId)** - Check checkbox/radio state before clicking

**Information Gathering:**
- **getInteractiveSnapshot(viewportOnly?)** - Get interactive elements. Use viewportOnly=false for full page
- **getPageContent()** - Get page text content

**User Intervention:**
- **requestUserAction(message, reason?)** - **REQUIRED when you need user help.** Use this tool (don't just ask in text) when you encounter:
  - CAPTCHA challenges
  - 2FA/OTP codes (authenticator apps, SMS codes, email verification)
  - Login pages requiring credentials you don't have
  - Cookie consent banners that won't respond to automation
  - Security checks or verifications
  - ANY situation where you need the user to manually do something
  **IMPORTANT:** Don't respond with text asking for help - CALL this tool instead! The workflow will pause, user completes the action, then you continue automatically.

**Tab Management:**
- **openNewTab(url?, purpose?)** - Open new tab
- **switchToTab(tabIndex)** - Switch tabs
- **closeTab(tabIndex?)** - Close tab
- **listTabs()** - List all tabs

**MULTI-PAGE FORM STRATEGY:**
1. Navigate to form URL — response includes `_snapshot.elements`
2. Fill all visible fields (multiple inputText calls in one turn is fine)
3. clickByText("Next") — response includes fresh `_snapshot.elements` for the next section
4. Repeat until form is submitted
5. After Submit, run checkFormErrors; the submit response also carries a snapshot you can use to confirm success

**Example - Multi-page Form:**
```
1. navigate(formUrl)                   → _snapshot shows Section 1 fields + "Next"
2. inputText(...)  (one call per field, same turn if possible)
3. clickByText("Next")                 → _snapshot shows Section 2 fields
4. inputText(...) for Section 2
5. clickByText("Submit")               → _snapshot shows confirmation or errors
6. checkFormErrors()
```

**WHEN TO USE clickByText vs click:**
- clickByText("Next") - For navigation buttons with known text
- clickByText("Submit") - For submit buttons
- click(nodeId) - For form fields, checkboxes, radio buttons

**BEFORE COMPLETING A TASK:**
- After clicking Submit, ALWAYS use checkFormErrors() to verify no errors occurred
- Take a final snapshot to confirm the success message or confirmation page
- If errors found, fix them and resubmit
- **If you need user help (2FA, CAPTCHA, manual login), CALL requestUserAction() - don't just respond with text!**

**COMPLETION:**
- Only respond with plain text (no tool calls) when the task is truly complete or impossible
- If you need user intervention, use requestUserAction() tool instead of completing
- Don't ask questions in your response - either use a tool or complete the task

Be decisive. If you see a "Next" button, click it. Don't keep scrolling looking for more content."""
    def chat_completion(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto"
    ) -> Any:
        """Call LLM with tool calling support"""
        
        if self.provider == "openai":
            return self._openai_completion(messages, tools, tool_choice)
        elif self.provider == "anthropic":
            return self._anthropic_completion(messages, tools, tool_choice)
        elif self.provider == "gemini":
            return self._gemini_completion(messages, tools, tool_choice)
    
    def _openai_completion(self, messages, tools, tool_choice):
        """OpenAI completion"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=0.3  # Lower temperature for more deterministic, efficient behavior
        )
        message = response.choices[0].message
        # Attach usage data to message
        if hasattr(response, 'usage') and response.usage:
            message.usage = {
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        return message
    
    def _anthropic_completion(self, messages, tools, tool_choice):
        """Anthropic completion - convert to their format"""
        # Convert OpenAI tool format to Anthropic format
        anthropic_tools = []
        for tool in tools:
            if tool['type'] == 'function':
                anthropic_tools.append({
                    'name': tool['function']['name'],
                    'description': tool['function']['description'],
                    'input_schema': tool['function']['parameters']
                })
        
        # Separate system message
        system_msg = next((m['content'] for m in messages if m['role'] == 'system'), '')
        user_messages = [m for m in messages if m['role'] != 'system']
        
        # Convert tool results to Anthropic format
        converted_messages = []
        for msg in user_messages:
            if msg['role'] == 'tool':
                # Convert tool results
                converted_messages.append({
                    'role': 'user',
                    'content': [{
                        'type': 'tool_result',
                        'tool_use_id': msg.get('tool_call_id', 'unknown'),
                        'content': msg['content']
                    }]
                })
            elif msg.get('tool_calls'):
                # Convert assistant message with tool calls
                content = []
                if msg.get('content'):
                    content.append({'type': 'text', 'text': msg['content']})
                for tc in msg['tool_calls']:
                    import json
                    content.append({
                        'type': 'tool_use',
                        'id': tc['id'],
                        'name': tc['function']['name'],
                        'input': json.loads(tc['function']['arguments'])
                    })
                converted_messages.append({
                    'role': 'assistant',
                    'content': content
                })
            else:
                converted_messages.append(msg)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_msg,
            messages=converted_messages,
            tools=anthropic_tools
        )
        
        # Convert response back to OpenAI format with usage data
        message = self._convert_anthropic_response(response)
        # Attach usage data
        if hasattr(response, 'usage') and response.usage:
            message.usage = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }
        return message
    
    def _convert_anthropic_response(self, response):
        """Convert Anthropic response to OpenAI format"""
        import json
        
        class Message:
            def __init__(self):
                self.content = None
                self.tool_calls = None
        
        msg = Message()
        
        # Extract content and tool calls
        text_content = []
        tool_calls = []
        
        for block in response.content:
            if block.type == 'text':
                text_content.append(block.text)
            elif block.type == 'tool_use':
                class ToolCall:
                    def __init__(self, id, name, arguments):
                        self.id = id
                        self.type = 'function'
                        self.function = type('obj', (object,), {
                            'name': name,
                            'arguments': json.dumps(arguments)
                        })()
                
                tool_calls.append(ToolCall(block.id, block.name, block.input))
        
        msg.content = ' '.join(text_content) if text_content else None
        msg.tool_calls = tool_calls if tool_calls else None
        
        return msg
    
    def _gemini_completion(self, messages, tools, tool_choice):
        """Gemini completion with function calling (google-genai SDK)"""
        import json
        gt = genai_types

        type_mapping = {
            'object': gt.Type.OBJECT,
            'string': gt.Type.STRING,
            'number': gt.Type.NUMBER,
            'integer': gt.Type.INTEGER,
            'boolean': gt.Type.BOOLEAN,
            'array': gt.Type.ARRAY,
        }

        def convert_property(prop_schema):
            prop_type = prop_schema.get('type', 'string')
            kwargs = {'type': type_mapping.get(prop_type, gt.Type.STRING)}
            if 'description' in prop_schema:
                kwargs['description'] = prop_schema['description']
            if 'enum' in prop_schema:
                kwargs['enum'] = prop_schema['enum']
            if prop_type == 'array' and 'items' in prop_schema:
                kwargs['items'] = convert_property(prop_schema['items'])
            if prop_type == 'object' and 'properties' in prop_schema:
                kwargs['properties'] = {
                    k: convert_property(v) for k, v in prop_schema['properties'].items()
                }
                if 'required' in prop_schema:
                    kwargs['required'] = prop_schema['required']
            return gt.Schema(**kwargs)

        def convert_schema_to_gemini(schema):
            if not schema or not isinstance(schema, dict):
                return None
            properties = schema.get('properties', {})
            if not properties:
                return None
            required = schema.get('required', [])
            return gt.Schema(
                type=type_mapping.get(schema.get('type', 'object'), gt.Type.OBJECT),
                properties={k: convert_property(v) for k, v in properties.items()},
                required=required if required else None,
            )

        function_declarations = []
        for tool in tools:
            if tool['type'] == 'function':
                func_def = tool['function']
                function_declarations.append(gt.FunctionDeclaration(
                    name=func_def['name'],
                    description=func_def['description'],
                    parameters=convert_schema_to_gemini(func_def.get('parameters', {})),
                ))
        gemini_tools = [gt.Tool(function_declarations=function_declarations)]
        tool_config = gt.ToolConfig(
            function_calling_config=gt.FunctionCallingConfig(mode='AUTO')
        )

        system_msg = next((m['content'] for m in messages if m['role'] == 'system'), '')

        contents = []
        for idx, msg in enumerate(messages):
            if msg['role'] == 'system':
                continue
            elif msg['role'] == 'user':
                contents.append(gt.Content(
                    role='user',
                    parts=[gt.Part(text=msg['content'] or '')],
                ))
            elif msg['role'] == 'assistant':
                cached = msg.get('_gemini_content')
                if cached is not None:
                    contents.append(cached)
                    continue
                parts = []
                if msg.get('content'):
                    parts.append(gt.Part(text=msg['content']))
                if msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        fc = gt.FunctionCall(
                            name=tc['function']['name'],
                            args=json.loads(tc['function']['arguments']),
                        )
                        part_kwargs = {'function_call': fc}
                        sig = tc.get('thought_signature')
                        if sig:
                            part_kwargs['thought_signature'] = sig
                        parts.append(gt.Part(**part_kwargs))
                if parts:
                    contents.append(gt.Content(role='model', parts=parts))
            elif msg['role'] == 'tool':
                tool_call_id = msg.get('tool_call_id', 'unknown')
                func_name = 'unknown'
                for prev_msg in reversed(messages[:idx]):
                    if prev_msg.get('tool_calls'):
                        for tc in prev_msg['tool_calls']:
                            if tc['id'] == tool_call_id:
                                func_name = tc['function']['name']
                                break
                        break
                try:
                    result_data = json.loads(msg['content'])
                    if not isinstance(result_data, dict):
                        result_data = {'result': result_data}
                except (ValueError, TypeError):
                    result_data = {'result': msg['content']}
                contents.append(gt.Content(
                    role='user',
                    parts=[gt.Part(function_response=gt.FunctionResponse(
                        name=func_name,
                        response=result_data,
                    ))],
                ))

        config = gt.GenerateContentConfig(
            system_instruction=system_msg if system_msg else None,
            tools=gemini_tools,
            tool_config=tool_config,
            temperature=0.3,
            max_output_tokens=4096,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        message = self._convert_gemini_response(response)
        usage = getattr(response, 'usage_metadata', None)
        if usage:
            message.usage = {
                'input_tokens': getattr(usage, 'prompt_token_count', 0) or 0,
                'output_tokens': getattr(usage, 'candidates_token_count', 0) or 0,
                'total_tokens': getattr(usage, 'total_token_count', 0) or 0,
            }
        return message
    
    def _convert_gemini_response(self, response):
        """Convert google-genai response to OpenAI-style message"""
        import json
        import uuid

        class Message:
            def __init__(self):
                self.content = None
                self.tool_calls = None

        msg = Message()
        text_content = []
        tool_calls = []

        candidates = getattr(response, 'candidates', None) or []
        if not candidates:
            msg.content = None
            msg.tool_calls = None
            return msg

        content = getattr(candidates[0], 'content', None)
        parts = getattr(content, 'parts', None) or [] if content else []
        msg._gemini_content = content

        class ToolCall:
            def __init__(self, id, name, arguments, thought_signature=None):
                self.id = id
                self.type = 'function'
                self.function = type('obj', (object,), {
                    'name': name,
                    'arguments': arguments,
                })()
                self.thought_signature = thought_signature

        for part in parts:
            if getattr(part, 'text', None):
                text_content.append(part.text)
            elif getattr(part, 'function_call', None):
                fc = part.function_call
                args_dict = dict(fc.args) if fc.args else {}
                sig = getattr(part, 'thought_signature', None) or None
                tool_calls.append(ToolCall(
                    f"call_{uuid.uuid4().hex[:8]}",
                    fc.name,
                    json.dumps(args_dict),
                    sig,
                ))

        msg.content = ' '.join(text_content) if text_content else None
        msg.tool_calls = tool_calls if tool_calls else None
        return msg
    
    def get_tools_definition(self) -> List[Dict[str, Any]]:
        """Define all available tools"""
        return [
            {
                'type': 'function',
                'function': {
                    'name': 'getInteractiveSnapshot',
                    'description': 'Get a snapshot of all interactive elements on the current page. This returns elements you can click or type into.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'viewportOnly': {
                                'type': 'boolean',
                                'description': 'Only return elements visible in viewport (recommended: true)',
                                'default': True
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'click',
                    'description': 'Click on an element by its nodeId from the interactive snapshot',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'nodeId': {
                                'type': 'integer',
                                'description': 'The nodeId of the element to click'
                            }
                        },
                        'required': ['nodeId']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'clickByText',
                    'description': 'Click on an element by its visible text. Use this for buttons like "Next", "Submit", "Continue", "Sign in" when nodeId-based clicking fails or for navigation buttons.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'text': {
                                'type': 'string',
                                'description': 'The visible text of the element to click (e.g., "Next", "Submit", "Continue")'
                            },
                            'elementType': {
                                'type': 'string',
                                'enum': ['button', 'link', 'any'],
                                'description': 'Type of element to look for. Use "any" if unsure.',
                                'default': 'any'
                            }
                        },
                        'required': ['text']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'inputText',
                    'description': 'Type text into an input field or text area',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'nodeId': {
                                'type': 'integer',
                                'description': 'The nodeId of the input element'
                            },
                            'text': {
                                'type': 'string',
                                'description': 'The text to type'
                            }
                        },
                        'required': ['nodeId', 'text']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'checkFormErrors',
                    'description': 'Check if there are any visible form validation errors on the page. Use this after clicking Submit to verify the form was submitted successfully, or to check why a form submission failed.',
                    'parameters': {
                        'type': 'object',
                        'properties': {}
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'selectDate',
                    'description': 'Select a date in a date picker field. Use this for date inputs instead of inputText. Handles various date picker formats.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'nodeId': {
                                'type': 'integer',
                                'description': 'The nodeId of the date input element'
                            },
                            'date': {
                                'type': 'string',
                                'description': 'Date in format YYYY-MM-DD or MM/DD/YYYY (e.g., "2024-01-15" or "01/15/2024")'
                            }
                        },
                        'required': ['nodeId', 'date']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'getElementState',
                    'description': 'Get the current state of an element (checked/unchecked, value, etc.). Use before clicking checkboxes or radios to avoid double-toggling.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'nodeId': {
                                'type': 'integer',
                                'description': 'The nodeId of the element to check'
                            }
                        },
                        'required': ['nodeId']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'selectDropdownOption',
                    'description': 'Select an option from a dropdown menu by its visible text. More reliable than clicking for dropdowns.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'nodeId': {
                                'type': 'integer',
                                'description': 'The nodeId of the dropdown element'
                            },
                            'optionText': {
                                'type': 'string',
                                'description': 'The visible text of the option to select'
                            }
                        },
                        'required': ['nodeId', 'optionText']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'navigate',
                    'description': 'Navigate to a URL',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'url': {
                                'type': 'string',
                                'description': 'The URL to navigate to (must include http:// or https://)'
                            }
                        },
                        'required': ['url']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'scrollDown',
                    'description': 'Scroll down the page by one viewport height',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'scrollUp',
                    'description': 'Scroll up the page by one viewport height',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'getPageContent',
                    'description': 'Get the text content of the current page',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'captureScreenshot',
                    'description': 'Take a screenshot of the current page',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'fullPage': {
                                'type': 'boolean',
                                'description': 'Capture full page or just viewport',
                                'default': False
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'sendKeys',
                    'description': 'Send a special key like Enter, Tab, Escape, etc.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'key': {
                                'type': 'string',
                                'description': 'Key to send: Enter, Tab, Escape, ArrowUp, ArrowDown, etc.',
                                'enum': ['Enter', 'Tab', 'Escape', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Backspace', 'Delete']
                            }
                        },
                        'required': ['key']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'getPageLoadStatus',
                    'description': 'Check if the page has finished loading',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            # Tab Management Tools
            {
                'type': 'function',
                'function': {
                    'name': 'openNewTab',
                    'description': 'Open a new browser tab, optionally navigating to a URL. Use this autonomously when: switching domains while preserving current page, working on parallel tasks, opening downloads, or organizing multi-step workflows.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'url': {
                                'type': 'string',
                                'description': 'Optional URL to navigate to in the new tab'
                            },
                            'purpose': {
                                'type': 'string',
                                'description': 'Purpose/description of this tab (e.g., "login", "download_assignment", "search_results") - helps with organization and context tracking'
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'switchToTab',
                    'description': 'Switch to a specific tab by its index (0-based)',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'tabIndex': {
                                'type': 'integer',
                                'description': 'Index of the tab to switch to (0 is the first tab)'
                            }
                        },
                        'required': ['tabIndex']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'closeTab',
                    'description': 'Close a specific tab or the current tab',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'tabIndex': {
                                'type': 'integer',
                                'description': 'Index of tab to close (omit to close current tab)'
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'listTabs',
                    'description': 'List all open tabs with their URLs, titles, purposes, and context summary. Use this to track your tab organization.',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'getNavigationContext',
                    'description': 'Get context about current navigation state to help decide if opening a new tab would be beneficial. Returns info about current domain, recent navigation patterns, and recommendations.',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'nextTab',
                    'description': 'Switch to the next tab (wraps around to first tab)',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'previousTab',
                    'description': 'Switch to the previous tab (wraps around to last tab)',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'goBack',
                    'description': 'Navigate back in the current tab\'s history',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'goForward',
                    'description': 'Navigate forward in the current tab\'s history',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'reloadTab',
                    'description': 'Reload/refresh a tab',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'tabIndex': {
                                'type': 'integer',
                                'description': 'Index of tab to reload (omit to reload current tab)'
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'closeOtherTabs',
                    'description': 'Close all tabs except the current one',
                    'parameters': {'type': 'object', 'properties': {}}
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'duplicateTab',
                    'description': 'Duplicate a tab by opening the same URL in a new tab',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'tabIndex': {
                                'type': 'integer',
                                'description': 'Index of tab to duplicate (omit to duplicate current tab)'
                            }
                        }
                    }
                }
            },
            # Google Sheets API Tools
            {
                'type': 'function',
                'function': {
                    'name': 'readSpreadsheet',
                    'description': 'Read values from a Google Spreadsheet using the Sheets API. Much faster and more reliable than browser navigation. Requires Google account to be connected.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'spreadsheetId': {
                                'type': 'string',
                                'description': 'The spreadsheet ID from the Google Sheets URL (the long string between /d/ and /edit)'
                            },
                            'range': {
                                'type': 'string',
                                'description': 'A1 notation range, e.g. "Sheet1!A1:D10" or "Sheet1" for entire sheet'
                            }
                        },
                        'required': ['spreadsheetId', 'range']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'writeSpreadsheet',
                    'description': 'Write values to a Google Spreadsheet. Overwrites existing data in the specified range. Values should be a 2D array (array of rows, each row is an array of cell values).',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'spreadsheetId': {
                                'type': 'string',
                                'description': 'The spreadsheet ID from the Google Sheets URL'
                            },
                            'range': {
                                'type': 'string',
                                'description': 'A1 notation range, e.g. "Sheet1!A1:D3"'
                            },
                            'values': {
                                'type': 'array',
                                'description': '2D array of values. E.g. [["Name","Age"],["Alice","30"],["Bob","25"]]',
                                'items': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'string'
                                    }
                                }
                            }
                        },
                        'required': ['spreadsheetId', 'range', 'values']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'appendRows',
                    'description': 'Append rows to the end of existing data in a Google Spreadsheet. Use this to add new data without overwriting.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'spreadsheetId': {
                                'type': 'string',
                                'description': 'The spreadsheet ID from the Google Sheets URL'
                            },
                            'range': {
                                'type': 'string',
                                'description': 'A1 notation range indicating where to append, e.g. "Sheet1!A:D"'
                            },
                            'values': {
                                'type': 'array',
                                'description': '2D array of row values to append',
                                'items': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'string'
                                    }
                                }
                            }
                        },
                        'required': ['spreadsheetId', 'range', 'values']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'createSpreadsheet',
                    'description': 'Create a new Google Spreadsheet. Returns the spreadsheet URL and ID.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'title': {
                                'type': 'string',
                                'description': 'Title of the new spreadsheet'
                            },
                            'sheetNames': {
                                'type': 'array',
                                'description': 'Optional list of sheet tab names. Defaults to ["Sheet1"].',
                                'items': {
                                    'type': 'string'
                                }
                            }
                        },
                        'required': ['title']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'getSheetsList',
                    'description': 'Get a list of all sheet tabs in a Google Spreadsheet, including their names, row counts, and column counts.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'spreadsheetId': {
                                'type': 'string',
                                'description': 'The spreadsheet ID from the Google Sheets URL'
                            }
                        },
                        'required': ['spreadsheetId']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'formatCells',
                    'description': 'Apply formatting to cells in a Google Spreadsheet (bold, colors, borders, column widths, etc.) using batchUpdate requests.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'spreadsheetId': {
                                'type': 'string',
                                'description': 'The spreadsheet ID from the Google Sheets URL'
                            },
                            'requests': {
                                'type': 'string',
                                'description': 'JSON-encoded array of Google Sheets API batchUpdate request objects. E.g. [{"repeatCell": {"range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1}, "cell": {"userEnteredFormat": {"textFormat": {"bold": true}}}, "fields": "userEnteredFormat.textFormat.bold"}}]'
                            }
                        },
                        'required': ['spreadsheetId', 'requests']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'uploadFileToBrowser',
                    'description': (
                        "Upload one of the user's attached files to a file input element on the current page. "
                        "Use this when a website has a file upload button (<input type=\"file\"> or a \"Choose file\" / \"Browse\" button) "
                        "and you need to attach a file the user provided. "
                        "First call getInteractiveSnapshot to find the file input's nodeId, then call this tool."
                    ),
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'nodeId': {
                                'type': 'integer',
                                'description': 'The nodeId of the file input element from getInteractiveSnapshot'
                            },
                            'fileName': {
                                'type': 'string',
                                'description': "The exact file name to upload — must match one of the names listed in [Attached Files] in the conversation"
                            }
                        },
                        'required': ['nodeId', 'fileName']
                    }
                }
            }
        ]
