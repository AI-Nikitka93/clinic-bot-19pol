import json
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

def diff_state(old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Tuple[list, list, list]:
    """
    Compares two parsed states and returns three lists of ticket events:
    - new_tickets: appeared in new_state but not in old_state
    - freed_tickets: ticket became available again (usually falls into new_tickets, but logic might differ if we track bookings)
    - booked_tickets: disappeared from new_state, means someone booked it.
    """
    new_tickets = []
    freed_tickets = []
    booked_tickets = []

    for spec_name, spec_data in new_state.items():
        old_spec = old_state.get(spec_name, {"doctors": {}})
        for doc_name, doc_data in spec_data["doctors"].items():
            old_doc = old_spec["doctors"].get(doc_name, {"tickets": {}})
            
            new_tix = set(doc_data["tickets"].keys())
            old_tix = set(old_doc["tickets"].keys())
            
            added = new_tix - old_tix
            removed = old_tix - new_tix
            
            for t_id in added:
                new_tickets.append({
                    "specialty": spec_name,
                    "doctor": doc_name,
                    "ticket_id": t_id,
                    "time": doc_data["tickets"][t_id]
                })
            
            for t_id in removed:
                booked_tickets.append({
                    "specialty": spec_name,
                    "doctor": doc_name,
                    "ticket_id": t_id,
                    "time": old_doc["tickets"][t_id]
                })

    return new_tickets, freed_tickets, booked_tickets

async def process_diff_and_notify(redis_client, new_state: Dict[str, Any]):
    # Get old state
    old_state_json = await redis_client.get("tickets_state")
    if old_state_json:
        old_state = json.loads(old_state_json)
    else:
        old_state = {}

    # Diff
    new_tix, freed_tix, booked_tix = diff_state(old_state, new_state)

    if new_tix or booked_tix:
        logger.info(f"Diff results: {len(new_tix)} new, {len(booked_tix)} booked.")
        events = {
            "new": new_tix,
            "booked": booked_tix
        }
        # Push to Pub/Sub
        await redis_client.publish("ticket_events", json.dumps(events, ensure_ascii=False))

    # Save new state
    await redis_client.set("tickets_state", json.dumps(new_state, ensure_ascii=False))
