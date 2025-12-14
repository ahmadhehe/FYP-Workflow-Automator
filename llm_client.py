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

You have access to these tools:

**Page Interaction:**
1. **getInteractiveSnapshot()** - Get all interactive elements on the current page
   Returns: List of elements with nodeId, type (clickable/typeable/selectable), name, role, position

2. **click(nodeId)** - Click on an element
   Use the nodeId from getInteractiveSnapshot

3. **inputText(nodeId, text)** - Type text into an input field
   Use for forms, search boxes, etc.

4. **navigate(url)** - Go to a URL
   Use to navigate to websites

5. **scrollDown()** / **scrollUp()** - Scroll the page

6. **getPageContent()** - Get the text content of the page
   Useful for reading information

7. **captureScreenshot()** - Take a screenshot
   Use when you need to see the page visually

8. **getPageLoadStatus()** - Check if page is fully loaded
   Use before taking actions on a new page

9. **sendKeys(key)** - Send special keys like "Enter", "Tab", "Escape"

**Tab Management (AUTONOMOUS):**
You should intelligently decide when to open new tabs without explicit user instructions. Open new tabs when:
- Navigating to a different domain/website while needing to preserve the current page
- Working on parallel tasks (e.g., comparing information, filling forms from different sources)
- Downloading files while continuing other work
- Opening links that should be kept separate from current workflow
- Switching between different accounts or contexts on the same site

10. **openNewTab(url?, purpose?)** - Open a new tab, optionally with URL and purpose description
11. **switchToTab(tabIndex)** - Switch to a specific tab by index
12. **closeTab(tabIndex?)** - Close a tab (current tab if no index specified)
13. **listTabs()** - List all open tabs with URLs, titles, and purposes
14. **getNavigationContext()** - Get context about current navigation to help decide if new tab needed
15. **nextTab()** / **previousTab()** - Navigate between tabs
16. **goBack()** / **goForward()** - Navigate browser history
17. **reloadTab(tabIndex?)** - Refresh a tab
18. **closeOtherTabs()** - Close all tabs except current
19. **duplicateTab(tabIndex?)** - Duplicate a tab

**Guidelines:**
- Always call getInteractiveSnapshot() FIRST to see what's on the page
- Use nodeId from the snapshot to interact with elements
- Wait for pages to load before taking actions
- Be methodical and explain each step
- If something fails, try alternative approaches
- Use getPageContent() to verify results
- When searching or submitting forms, use sendKeys("Enter") after typing

**AUTONOMOUS TAB MANAGEMENT - IMPORTANT:**
- You can and SHOULD open new tabs proactively when it makes sense
- Call getNavigationContext() when considering whether to navigate away from current page
- Open new tabs BEFORE navigating to preserve context (e.g., "openNewTab(url, purpose='download assignment')")
- Use tab purposes to organize your work (e.g., purpose='login', 'search_results', 'download_page')
- Think: "Will I need this page again?" → If yes, open in new tab
- Think: "Am I switching to a different task?" → If yes, consider new tab
- When working across multiple sites, use separate tabs for better organization
- Call listTabs() periodically to track your open tabs
- Close tabs when you're done with them to stay organized

**Example workflow:**
1. Call getInteractiveSnapshot() to see the page
2. Identify the element you need (e.g., search box)
3. Use click() or inputText() with the correct nodeId
4. Verify the action succeeded
5. Continue to next step

**Multi-tab workflow examples:**
Example 1 - Preserving context:
1. On page A, need to go to page B but will return to A
2. openNewTab(url_B, purpose='temporary_task') - DON'T navigate current tab away
3. Work in new tab
4. switchToTab(0) to return to original context

Example 2 - Parallel tasks:
1. Working on task requiring info from multiple sources
2. openNewTab(source1, purpose='reference_data')
3. openNewTab(source2, purpose='form_to_fill')
4. switchToTab() between them as needed
5. Close tabs when done

Example 3 - Downloads:
1. On a page with download link
2. openNewTab(download_url, purpose='download') - keep original page accessible
3. switchToTab(0) to continue work while download proceeds

Think step by step and be precise with element selection."""

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
            temperature=0.7
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
            
            schema_type = schema.get('type', 'object')
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            # If no properties, return None (Gemini doesn't like empty schemas)
            if not properties:
                return None
            
            # Convert properties to Gemini Schema format
            gemini_properties = {}
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get('type', 'string')
                prop_kwargs = {
                    'type': type_mapping.get(prop_type, protos.Type.STRING)
                }
                if 'description' in prop_schema:
                    prop_kwargs['description'] = prop_schema['description']
                if 'enum' in prop_schema:
                    prop_kwargs['enum'] = prop_schema['enum']
                if 'default' in prop_schema:
                    # Gemini doesn't support default directly, skip it
                    pass
                gemini_properties[prop_name] = protos.Schema(**prop_kwargs)
            
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
        model_with_system = genai.GenerativeModel(
            self.model,
            system_instruction=system_msg,
            tools=gemini_tools
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
                
                # Convert Gemini's MapComposite args to a regular dict
                # fc.args is a special proto object, need to convert it properly
                try:
                    if hasattr(fc.args, 'items'):
                        # It's a dict-like object
                        args_dict = dict(fc.args.items())
                    elif hasattr(fc.args, '_pb'):
                        # It's a protobuf object, convert via MessageToDict
                        from google.protobuf.json_format import MessageToDict
                        args_dict = MessageToDict(fc.args._pb)
                    else:
                        # Try to convert it as-is
                        args_dict = dict(fc.args) if fc.args else {}
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
            }
        ]
