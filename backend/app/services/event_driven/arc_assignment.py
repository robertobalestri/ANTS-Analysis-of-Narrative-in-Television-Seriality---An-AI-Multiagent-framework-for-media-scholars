"""Arc assignment service - assigns narrative arcs to events via LLM."""
import json
import re
from typing import List
from app.models.narrative_event import NarrativeEvent
from app.core.logging import setup_logging

logger = setup_logging(__name__)

ARC_ASSIGNMENT_PROMPT = """
You are analyzing narrative events from a TV episode and assigning them to existing narrative arcs.

Given:
1. A list of narrative ARCS (with their titles and descriptions)
2. A list of BEATS/EVENTS (narrative events extracted from the episode)

Task: For each event, determine which arc(s) it belongs to.

Rules:
- An event can belong to ONE or MORE arcs
- Events that don't clearly fit any arc can be marked "unassigned"
- Use the arc's title, description, and main characters to decide
- Consider the event's content and characters involved

Return JSON:
{{
  "assignments": [
    {{"event_index": 0, "arc_ids": ["abc123", "def456"]}},
    {{"event_index": 1, "arc_ids": ["abc123"]}},
    {{"event_index": 2, "arc_ids": []}}
  ]
}}

CRITICAL: Use the EXACT arc IDs from the list above (e.g., "abc123", not "Romeo's Love").

Example:
- Arc ID: "arc-001", Title: "Romeo's Love"
- Event 0: "Romeo meets Juliet"
- Assignment: {{"event_index": 0, "arc_ids": ["arc-001"]}}
"""


async def assign_arcs_to_events(
    events: List[NarrativeEvent],
    arcs: List[dict],
) -> List[List[str]]:
    """
    Assign arcs to events using LLM.

    Returns:
        List of arc_ids per event, same length as input events.
    """
    if not events or not arcs:
        return [[] for _ in events]

    from app.services.ai.models import get_llm
    from langchain_core.messages import HumanMessage

    llm = get_llm()

    # Build prompt
    arcs_text = "\n".join([
        f"- ID: {arc['id']} | Title: {arc['title']} | Desc: {arc['description']} | Chars: {', '.join(arc.get('main_characters', []))}"
        for arc in arcs
    ])

    events_text = "\n".join([
        f"[{i}] {e.content[:200]} (chars: {', '.join(e.characters[:3])})"
        for i, e in enumerate(events)
    ])

    prompt = f"""Given these existing arcs:
{arcs_text}

And these events from the episode:
{events_text}

{ARC_ASSIGNMENT_PROMPT}
"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw_content = response.content if hasattr(response, "content") else str(response)

        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            logger.warning(f"Failed to parse assignments from LLM response: {raw_content[:500]}")
            return [[] for _ in events]

        assignments = parsed.get("assignments", [])
        result = []
        for i in range(len(events)):
            match = next((a for a in assignments if a.get("event_index") == i), None)
            if match:
                result.append(match.get("arc_ids", []))
            else:
                result.append([])

        logger.info(f"Assigned arcs to {len(events)} events")
        return result

    except Exception as e:
        logger.error(f"Failed to assign arcs: {e}")
        return [[] for _ in events]


def update_events_with_arcs(events: List[NarrativeEvent], assignments: List[List[str]]) -> List[NarrativeEvent]:
    """Update events with their assigned arc_ids."""
    for event, arc_ids in zip(events, assignments):
        event.arc_ids = arc_ids
    return events