"""
LLM Client - Unified interface for different LLM providers
"""
from typing import List, Dict, Any, Optional
import os
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai


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
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            self.client = genai.GenerativeModel(self.model)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def get_system_prompt(self) -> str:
        """System prompt that defines agent behavior"""
        return """You are a browser automation agent. Your job is to help users complete tasks on websites by controlling a web browser.

**CRITICAL RULES - READ CAREFULLY:**
1. NEVER call getInteractiveSnapshot twice in a row! After getting a snapshot, you MUST take an action (click, inputText, etc.)
2. When you see form fields in a snapshot - FILL THEM using inputText or click
3. When you see a "Next", "Continue", "Submit" button - CLICK IT using clickByText()
4. If you just called getInteractiveSnapshot, your next action MUST be inputText, click, clickByText, or similar
5. Multi-page forms: Fill visible fields → click "Next" → snapshot → fill next fields → repeat

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

**Tab Management:**
- **openNewTab(url?, purpose?)** - Open new tab
- **switchToTab(tabIndex)** - Switch tabs
- **closeTab(tabIndex?)** - Close tab
- **listTabs()** - List all tabs

**MULTI-PAGE FORM STRATEGY:**
1. Navigate to form URL
2. getInteractiveSnapshot() to see what's available
3. If you see form fields - fill them
4. If you see a "Next" button - click it with clickByText("Next")
5. After clicking Next, take a new snapshot to see the next section
6. Repeat until form is submitted

**Example - Multi-page Form:**
```
1. navigate(formUrl)
2. getInteractiveSnapshot() → see Section 1 fields + "Next" button
3. Fill Section 1 fields
4. clickByText("Next")  ← IMPORTANT: Use this for navigation!
5. getInteractiveSnapshot() → see Section 2 fields
6. Fill Section 2 fields
7. clickByText("Submit")
8. checkFormErrors() → ALWAYS check for errors after Submit!
9. getInteractiveSnapshot() → Verify success message or confirmation
```

**WHEN TO USE clickByText vs click:**
- clickByText("Next") - For navigation buttons with known text
- clickByText("Submit") - For submit buttons
- click(nodeId) - For form fields, checkboxes, radio buttons

**BEFORE COMPLETING A TASK:**
- After clicking Submit, ALWAYS use checkFormErrors() to verify no errors occurred
- Take a final snapshot to confirm the success message or confirmation page
- If errors found, fix them and resubmit

Be decisive. If you see a "Next" button, click it. Don't keep scrolling looking for more content.

**GOOGLE SHEETS API TOOLS:**
You have direct API access to Google Sheets (if the user has connected their Google account). These are MUCH faster and more reliable than manipulating sheets through the browser.

- **readSpreadsheet(spreadsheetId, range)** - Read cell values. Range uses A1 notation: "Sheet1!A1:D10"
- **writeSpreadsheet(spreadsheetId, range, values)** - Write/overwrite cells. Values is a 2D array.
- **appendRows(spreadsheetId, range, values)** - Append rows after existing data.
- **createSpreadsheet(title, sheetNames?)** - Create a new spreadsheet. Returns URL and ID.
- **getSheetsList(spreadsheetId)** - List all sheet tabs in a spreadsheet.
- **formatCells(spreadsheetId, requests)** - Apply formatting (bold, colors, borders, etc.)

**How to get spreadsheetId from a URL:**
From `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit` → spreadsheetId is `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`

**When to use Sheets API vs Browser:**
- USE API TOOLS for: reading data, writing data, creating sheets, bulk operations
- USE BROWSER for: sharing settings, adding comments, complex chart interactions
- If Sheets API returns an auth error, tell the user to connect their Google account in Settings.

**Example - API workflow:**
1. User says "Read data from [sheets URL]"
2. Extract spreadsheetId from URL
3. getSheetsList(spreadsheetId) → see available tabs
4. readSpreadsheet(spreadsheetId, "Sheet1!A1:Z100") → get data
5. Respond with summary"""

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
        """Gemini completion with function calling"""
        import json
        import uuid
        from google.generativeai import protos
        
        def convert_schema_to_gemini(schema):
            """Convert OpenAI-style JSON schema to Gemini protos.Schema format"""
            if not schema or not isinstance(schema, dict):
                return None
            
            # Map OpenAI types to Gemini types
            type_mapping = {
                'object': protos.Type.OBJECT,
                'string': protos.Type.STRING,
                'number': protos.Type.NUMBER,
                'integer': protos.Type.INTEGER,
                'boolean': protos.Type.BOOLEAN,
                'array': protos.Type.ARRAY,
            }
            
            def convert_property(prop_schema):
                """Recursively convert a single property schema to Gemini format"""
                prop_type = prop_schema.get('type', 'string')
                prop_kwargs = {
                    'type': type_mapping.get(prop_type, protos.Type.STRING)
                }
                if 'description' in prop_schema:
                    prop_kwargs['description'] = prop_schema['description']
                if 'enum' in prop_schema:
                    prop_kwargs['enum'] = prop_schema['enum']
                
                # Handle array items recursively
                if prop_type == 'array' and 'items' in prop_schema:
                    items_schema = prop_schema['items']
                    prop_kwargs['items'] = convert_property(items_schema)
                
                # Handle nested objects with properties
                if prop_type == 'object' and 'properties' in prop_schema:
                    nested_props = {}
                    for nested_name, nested_schema in prop_schema['properties'].items():
                        nested_props[nested_name] = convert_property(nested_schema)
                    prop_kwargs['properties'] = nested_props
                    if 'required' in prop_schema:
                        prop_kwargs['required'] = prop_schema['required']
                
                return protos.Schema(**prop_kwargs)
            
            schema_type = schema.get('type', 'object')
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            # If no properties, return None (Gemini doesn't like empty schemas)
            if not properties:
                return None
            
            # Convert properties to Gemini Schema format
            gemini_properties = {}
            for prop_name, prop_schema in properties.items():
                gemini_properties[prop_name] = convert_property(prop_schema)
            
            return protos.Schema(
                type=type_mapping.get(schema_type, protos.Type.OBJECT),
                properties=gemini_properties,
                required=required if required else None
            )
        
        # Convert OpenAI tool format to Gemini format
        gemini_tools = []
        for tool in tools:
            if tool['type'] == 'function':
                func_def = tool['function']
                params = func_def.get('parameters', {})
                
                gemini_schema = convert_schema_to_gemini(params)
                
                gemini_tools.append(protos.FunctionDeclaration(
                    name=func_def['name'],
                    description=func_def['description'],
                    parameters=gemini_schema
                ))
        
        # Build Gemini tool config
        from google.generativeai.types import content_types
        tool_config = content_types.to_tool_config({
            'function_calling_config': {'mode': 'AUTO'}
        })
        
        # Convert messages to Gemini format
        # Separate system message and build conversation history
        system_msg = next((m['content'] for m in messages if m['role'] == 'system'), '')
        
        # Create a new model with system instruction for this request
        # Use lower temperature for more deterministic behavior
        generation_config = genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=4096
        )
        
        model_with_system = genai.GenerativeModel(
            self.model,
            system_instruction=system_msg,
            tools=gemini_tools,
            generation_config=generation_config
        )
        
        # Build chat history
        gemini_history = []
        for msg in messages:
            if msg['role'] == 'system':
                continue  # Already handled as system instruction
            elif msg['role'] == 'user':
                gemini_history.append({
                    'role': 'user',
                    'parts': [{'text': msg['content']}]
                })
            elif msg['role'] == 'assistant':
                parts = []
                if msg.get('content'):
                    parts.append({'text': msg['content']})
                if msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        parts.append({
                            'function_call': {
                                'name': tc['function']['name'],
                                'args': json.loads(tc['function']['arguments'])
                            }
                        })
                if parts:
                    gemini_history.append({
                        'role': 'model',
                        'parts': parts
                    })
            elif msg['role'] == 'tool':
                # Tool results in Gemini format
                tool_call_id = msg.get('tool_call_id', 'unknown')
                # Find the function name from the previous assistant message
                func_name = 'unknown'
                for prev_msg in reversed(messages[:messages.index(msg)]):
                    if prev_msg.get('tool_calls'):
                        for tc in prev_msg['tool_calls']:
                            if tc['id'] == tool_call_id:
                                func_name = tc['function']['name']
                                break
                        break
                
                try:
                    result_data = json.loads(msg['content'])
                except:
                    result_data = {'result': msg['content']}
                
                gemini_history.append({
                    'role': 'user',
                    'parts': [{
                        'function_response': {
                            'name': func_name,
                            'response': result_data
                        }
                    }]
                })
        
        # Start chat and get response
        chat = model_with_system.start_chat(history=gemini_history[:-1] if gemini_history else [])
        
        # Get the last message to send
        if gemini_history:
            last_msg = gemini_history[-1]
            response = chat.send_message(last_msg['parts'], tool_config=tool_config)
        else:
            response = chat.send_message("Hello", tool_config=tool_config)
        
        # Convert response back to OpenAI format with usage data
        message = self._convert_gemini_response(response)
        # Attach usage data
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            message.usage = {
                'input_tokens': response.usage_metadata.prompt_token_count,
                'output_tokens': response.usage_metadata.candidates_token_count,
                'total_tokens': response.usage_metadata.total_token_count
            }
        return message
    
    def _convert_gemini_response(self, response):
        """Convert Gemini response to OpenAI format"""
        import json
        import uuid
        
        class Message:
            def __init__(self):
                self.content = None
                self.tool_calls = None
        
        msg = Message()
        
        # Extract content and function calls
        text_content = []
        tool_calls = []
        
        for part in response.parts:
            if hasattr(part, 'text') and part.text:
                text_content.append(part.text)
            elif hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                
                # Convert Gemini's proto-plus args to a regular Python dict
                # fc.args is a Struct-like proto object; we recursively convert it
                def _proto_to_python(val):
                    """Recursively convert protobuf/proto-plus values to native Python"""
                    if val is None:
                        return None
                    if isinstance(val, (str, int, float, bool)):
                        return val
                    # Dict-like (Struct, MapComposite)
                    if hasattr(val, 'items') and callable(getattr(val, 'items')):
                        return {str(k): _proto_to_python(v) for k, v in val.items()}
                    # List-like (ListValue, RepeatedComposite)
                    if hasattr(val, '__iter__'):
                        try:
                            return [_proto_to_python(item) for item in val]
                        except TypeError:
                            return str(val)
                    return val
                
                try:
                    args_dict = _proto_to_python(fc.args) or {}
                except Exception as e:
                    print(f"Warning: Failed to convert Gemini args: {e}")
                    args_dict = {}
                
                class ToolCall:
                    def __init__(self, id, name, arguments):
                        self.id = id
                        self.type = 'function'
                        self.function = type('obj', (object,), {
                            'name': name,
                            'arguments': arguments
                        })()
                
                tool_calls.append(ToolCall(
                    f"call_{uuid.uuid4().hex[:8]}",
                    fc.name,
                    json.dumps(args_dict)
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
            }
        ]
