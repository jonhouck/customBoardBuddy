import asyncio
import json
from ingestion.legistar_bulk_load import fetch_event_items

# March 10 OWA Committee Meeting is EventID 1681
items = fetch_event_items(1681)
print(f"Total items: {len(items)}")

# Find the item talking about Richardson
found = False
for item in items:
    if "Richardson" in item.get("EventItemTitle", ""):
        print("Found Richardson item!")
        from pprint import pprint
        pprint(item)
        found = True
        break

if not found:
    print("Could not find Richardson item in event 1681 items.")
