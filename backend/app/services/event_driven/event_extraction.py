"""Event extraction agent for beat-level narrative analysis."""
import json
import re
import uuid
from typing import List, Optional
from textwrap import dedent

from app.models.narrative_event import NarrativeEvent, EventType
from app.services.ai.models import get_llm
from app.utils.srt import parse_srt, entries_to_text
from langchain_core.messages import HumanMessage
from app.core.logging import setup_logging

logger = setup_logging(__name__)

BEAT_EXTRACTION_PROMPT = dedent("""
You are analyzing a TV episode transcript (SRT format).
Extract 20-30 BEAT-LEVEL narrative events. A beat is a single, small narrative unit
(e.g., a single scene, a single character action, a single dialogue exchange).

For each event, return JSON with these fields:
- beat_number: int (1-based)
- content: str (1-2 sentences describing what happens)
- characters: List[str] (characters present in this beat)
- srt_start: int (0-based SRT entry index where this beat starts)
- srt_end: int (0-based SRT entry index where this beat ends)

Rules:
- Extract 20-30 events per episode (aim for ~25)
- Each beat should cover ~30-60 seconds of screen time
- Include: character entrances/exits, plot developments, emotional beats
- Merge very short dialogues into single beats
- Skip purely transitional scenes with no narrative content
- Mark the final event of an episode with "episode_cliffhanger" or "episode_resolution" in the content

Output: JSON array of events, wrapped in ```json code blocks
Example response format:
```json
[
  {"beat_number": 1, "content": "Jane discovers a mysterious letter in her mailbox", "characters": ["Jane"], "srt_start": 0, "srt_end": 3},
  {"beat_number": 2, "content": "Jane shows the letter to her neighbor Bob", "characters": ["Jane", "Bob"], "srt_start": 4, "srt_end": 8}
]
```
""")


async def extract_events_from_srt(
    srt_content: str,
    episode_ref: str,
    series: str = "unknown"
) -> List[NarrativeEvent]:
    """
    Extract beat-level events from SRT transcript using LLM.

    Args:
        srt_content: Raw SRT transcript content
        episode_ref: Episode reference (e.g., "S1E3")
        series: Series name

    Returns:
        List of NarrativeEvent objects
    """
    llm = get_llm()

    # Parse SRT to get entry count and text
    srt_entries = parse_srt(srt_content)
    if not srt_entries:
        logger.warning("No SRT entries found in content")
        return []

    srt_text = entries_to_text(srt_entries)

    prompt = dedent(f"""
    Series: {series}
    Episode: {episode_ref}

    {BEAT_EXTRACTION_PROMPT}

    Total SRT entries: {len(srt_entries)}
    Extract events from the following transcript:

    {srt_text}
    """)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw_content = response.content if hasattr(response, "content") else str(response)

            # Extract JSON from response
            json_match = re.search(r'\[.*\]', raw_content, re.DOTALL)
            if not json_match:
                json_match = re.search(r'```json\s*(.*?)\s*```', raw_content, re.DOTALL)

            if json_match:
                json_str = json_match.group(0) if '```' not in json_match.group(0) else json_match.group(1)
                events_data = json.loads(json_str)
            else:
                raise ValueError("Failed to parse events from LLM response (no JSON array found)")

            # Validate the parsed data for timestamp correctness
            for i, event_data in enumerate(events_data):
                srt_start = event_data.get("srt_start", 0)
                srt_end = event_data.get("srt_end", srt_start)
                if srt_start > srt_end:
                    raise ValueError(f"Event {i+1} has reversed timestamps: srt_start ({srt_start}) > srt_end ({srt_end})")
                if srt_start >= len(srt_entries) or srt_end >= len(srt_entries):
                    raise ValueError(f"Event {i+1} has out of bounds indices. Max valid index: {len(srt_entries)-1}")

            # Convert to NarrativeEvent objects
            events = []
            for event_data in events_data:
                beat_number = event_data.get("beat_number", len(events) + 1)
                content = event_data.get("content", "")
                characters = event_data.get("characters", [])
                srt_start = event_data.get("srt_start", 0)
                srt_end = event_data.get("srt_end", srt_start)

                start_time = srt_entries[srt_start].start_time
                end_time = srt_entries[srt_end].end_time

                event = NarrativeEvent(
                    id=f"{episode_ref}_beat_{beat_number:02d}_{uuid.uuid4().hex[:8]}",
                    episode_ref=episode_ref,
                    content=content,
                    characters=characters,
                    event_type=EventType.ATOMIC,
                    srt_start_index=srt_start,
                    srt_end_index=srt_end,
                    srt_start_time=start_time,
                    srt_end_time=end_time,
                )
                events.append(event)

            logger.info(f"Extracted {len(events)} events from {episode_ref} on attempt {attempt+1}")
            return events

        except Exception as e:
            logger.warning(f"Error extracting events on attempt {attempt+1}/{max_retries}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed all {max_retries} attempts to extract events.")
                return []