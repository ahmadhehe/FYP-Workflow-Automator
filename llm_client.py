"""
LLM Client - Unified interface for different LLM providers
"""
from typing import List, Dict, Any, Optional
import os
from openai import OpenAI
from anthropic import Anthropic


class LLMClient:
    def __init__(self, provider: str = "openai"):
        self.provider = provider
        
        if provider == "openai":
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        elif provider == "anthropic":
            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def get_system_prompt(self) -> str:
        """System prompt that defines agent behavior"""
        return """You are a browser automation agent. Your job is to help users complete tasks on websites by controlling a web browser.

You have access to these tools:

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

**Guidelines:**
- Always call getInteractiveSnapshot() FIRST to see what's on the page
- Use nodeId from the snapshot to interact with elements
- Wait for pages to load before taking actions
- Be methodical and explain each step
- If something fails, try alternative approaches
- Use getPageContent() to verify results
- When searching or submitting forms, use sendKeys("Enter") after typing

**Example workflow:**
1. Call getInteractiveSnapshot() to see the page
2. Identify the element you need (e.g., search box)
3. Use click() or inputText() with the correct nodeId
4. Verify the action succeeded
5. Continue to next step

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
    
    def _openai_completion(self, messages, tools, tool_choice):
        """OpenAI completion"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=0.7
        )
        return response.choices[0].message
    
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
        
        # Convert response back to OpenAI format
        return self._convert_anthropic_response(response)
    
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
            }
        ]
