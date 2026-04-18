"""
File-based flow history storage helpers.
"""
import json
import os
from typing import List, Dict, Any

FLOWS_FILE = "flows_history.json"


def load_flows() -> List[Dict[str, Any]]:
    if os.path.exists(FLOWS_FILE):
        try:
            with open(FLOWS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_flows(flows: List[Dict[str, Any]]):
    with open(FLOWS_FILE, 'w') as f:
        json.dump(flows, f, indent=2, default=str)


def save_flow(flow: Dict[str, Any]):
    """Add or update a flow (keeps last 50)."""
    flows = load_flows()
    existing_idx = next((i for i, f in enumerate(flows) if f['id'] == flow['id']), None)
    if existing_idx is not None:
        flows[existing_idx] = flow
    else:
        flows.insert(0, flow)
    flows = flows[:50]
    save_flows(flows)
