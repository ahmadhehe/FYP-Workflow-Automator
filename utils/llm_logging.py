"""
LLM interaction logging and cost calculation utilities.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

LLM_LOG_DIR = Path("llm_logs")
LLM_LOG_DIR.mkdir(exist_ok=True)

# Pricing per 1M tokens (as of Dec 2024)
PRICING = {
    "openai": {"input": 10.00, "output": 30.00},
    "anthropic": {"input": 3.00, "output": 15.00},
    "gemini": {"input": 0.075, "output": 0.30},
}


def setup_llm_logger(flow_id: str) -> logging.Logger:
    """Create a per-workflow logger that writes to llm_logs/<flow_id>.log."""
    logger = logging.getLogger(f"llm_interaction_{flow_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    log_file = LLM_LOG_DIR / f"{flow_id}.log"
    handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    return logger


def log_llm_interaction(logger: logging.Logger, iteration: int, messages: List[Dict], response: Any, provider: str):
    """Log a single LLM call with tokens and estimated cost."""
    logger.info(f"\n{'='*80}")
    logger.info(f"ITERATION {iteration} - Provider: {provider}")
    logger.info(f"{'='*80}\n")

    logger.info("INPUT MESSAGES:")
    for i, msg in enumerate(messages):
        logger.info(f"\n--- Message {i+1} ({msg.get('role', 'unknown')}) ---")
        if msg.get('content'):
            content = msg['content']
            if len(content) > 1000:
                logger.info(f"{content[:500]}...\n[TRUNCATED {len(content)} chars total]\n...{content[-500:]}")
            else:
                logger.info(content)
        if msg.get('tool_calls'):
            loggable = [{k: v for k, v in tc.items() if not isinstance(v, (bytes, bytearray))} for tc in msg['tool_calls']]
            logger.info(f"Tool Calls: {json.dumps(loggable, indent=2, default=str)}")

    logger.info(f"\n{'='*40}")
    logger.info("LLM RESPONSE:")
    logger.info(f"{'='*40}\n")
    if hasattr(response, 'content') and response.content:
        logger.info(f"Content: {response.content}")
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info("\nTool Calls:")
        for tc in response.tool_calls:
            logger.info(f"  - {tc.function.name}: {tc.function.arguments}")

    if hasattr(response, 'usage') and response.usage:
        input_tokens = response.usage.get('input_tokens', 0)
        output_tokens = response.usage.get('output_tokens', 0)
        p = PRICING.get(provider, PRICING["openai"])
        cost = (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]
        logger.info(f"\n{'='*40}")
        logger.info("TOKEN USAGE:")
        logger.info(f"Input tokens:  {input_tokens:,}")
        logger.info(f"Output tokens: {output_tokens:,}")
        logger.info(f"Total tokens:  {response.usage.get('total_tokens', 0):,}")
        logger.info(f"\nCost for this call: ${cost:.6f}")

    logger.info(f"\n{'='*80}\n")


def calculate_cost(provider: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
    """Return input_cost, output_cost, total_cost for a given provider + token counts."""
    pricing = PRICING.get(provider, PRICING["openai"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + output_cost,
    }


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4
