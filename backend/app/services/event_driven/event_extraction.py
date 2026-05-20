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

CRITICAL TRANSCRIPT INDEX CONSTRAINTS:
1. You are given the total number of SRT entries (let's call it N).
2. The indices 'srt_start' and 'srt_end' MUST satisfy: 0 <= srt_start <= srt_end <= N-1.
3. NEVER return an index greater than or equal to N (the maximum valid index is N-1).
4. The indices must be sequential and chronological. For example, if beat 1 ends at index 10, beat 2 should start at index 11.
5. Every single event must have 'srt_start' less than or equal to 'srt_end' (srt_start <= srt_end).

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
    Uses progressive slicing to recover from partial failures and retry only the remaining segment.

    Args:
        srt_content: Raw SRT transcript content
        episode_ref: Episode reference (e.g., "S1E3")
        series: Series name

    Returns:
        List of NarrativeEvent objects
    """
    llm = get_llm()

    # Parse SRT to get entry count
    srt_entries = parse_srt(srt_content)
    if not srt_entries:
        logger.warning("No SRT entries found in content")
        return []

    all_valid_events: List[NarrativeEvent] = []
    current_start_idx = 0
    N = len(srt_entries)
    
    max_loops = 5
    loop_count = 0
    
    while current_start_idx < N and loop_count < max_loops:
        loop_count += 1
        remaining_entries = srt_entries[current_start_idx:]
        
        # Format remaining transcript with absolute 0-based indices in brackets
        lines = []
        for idx, entry in enumerate(remaining_entries):
            abs_idx = current_start_idx + idx
            lines.append(f"[{abs_idx}] {entry.content}")
        srt_text = "\n".join(lines)
        
        # Determine target events remaining
        target_events_count = max(1, 25 - len(all_valid_events))
        if target_events_count > len(remaining_entries):
            target_events_count = len(remaining_entries)
            
        prompt = dedent(f"""
        Series: {series}
        Episode: {episode_ref}

        You are analyzing a TV episode transcript (SRT format) starting from index {current_start_idx} to the end.
        We have already successfully extracted {len(all_valid_events)} events for the earlier part of the episode.
        Now, please extract the remaining beat-level narrative events for the rest of the transcript.
        Extract approximately {target_events_count} events for this remaining section.

        For each event, return JSON with these fields:
        - beat_number: int (1-based, continue the sequence from {len(all_valid_events) + 1})
        - content: str (1-2 sentences describing what happens)
        - characters: List[str] (characters present in this beat)
        - srt_start: int (The bracketed number [] in the transcript where this beat starts)
        - srt_end: int (The bracketed number [] in the transcript where this beat ends)

        Rules:
        - Each beat should cover ~30-60 seconds of screen time.
        - Merge very short dialogues into single beats.
        - Skip purely transitional scenes with no narrative content.
        - If this section reaches the end of the episode, mark the final event of the episode with "episode_cliffhanger" or "episode_resolution" in the content.

        CRITICAL TRANSCRIPT INDEX CONSTRAINTS:
        1. You MUST only use the exact index numbers shown inside the brackets [] in the transcript below (from {current_start_idx} to {N-1}).
        2. Every srt_start and srt_end MUST satisfy: {current_start_idx} <= srt_start <= srt_end <= {N-1}.
        3. Never output any indices outside this range.
        4. Every single event must have srt_start <= srt_end.
        5. The indices must be sequential and chronological.

        Output: JSON array of events, wrapped in ```json code blocks.
        
        Example response format:
        ```json
        [
          {{"beat_number": {len(all_valid_events) + 1}, "content": "Jane discovers a mysterious letter in her mailbox", "characters": ["Jane"], "srt_start": {current_start_idx}, "srt_end": {current_start_idx + 3}}}
        ]
        ```

        Total SRT entries remaining: {len(remaining_entries)}
        Extract remaining events from the following transcript:

        {srt_text}
        """)

        slice_success = False
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

                if not isinstance(events_data, list):
                    raise ValueError("LLM response is not a JSON array")

                if len(events_data) == 0:
                    raise ValueError("LLM response returned an empty list of events")

                # Validate the parsed data for index correctness chronologically
                valid_slice_events = []
                for i, event_data in enumerate(events_data):
                    try:
                        srt_start = event_data.get("srt_start")
                        srt_end = event_data.get("srt_end")
                        if srt_start is None or srt_end is None:
                            raise ValueError("Event is missing srt_start or srt_end")
                        
                        srt_start = int(srt_start)
                        srt_end = int(srt_end)
                        
                        if srt_start > srt_end:
                            raise ValueError(f"Event has reversed timestamps: srt_start ({srt_start}) > srt_end ({srt_end})")
                        
                        # Must be within the remaining slice range
                        if srt_start < current_start_idx or srt_end >= N:
                            raise ValueError(f"Event has indices outside the valid range [{current_start_idx}, {N-1}]: srt_start={srt_start}, srt_end={srt_end}")
                        
                        event_data["srt_start"] = srt_start
                        event_data["srt_end"] = srt_end
                        valid_slice_events.append(event_data)
                    except Exception as e:
                        logger.warning(f"Validation failed for event {i+1} at index {current_start_idx}: {e}")
                        # Keep the sequence of valid events before this failure point
                        break

                if len(valid_slice_events) > 0:
                    # Sort by start index
                    valid_slice_events.sort(key=lambda x: x["srt_start"])
                    
                    # Convert to NarrativeEvent objects and append
                    for event_data in valid_slice_events:
                        beat_number = len(all_valid_events) + 1
                        content = event_data.get("content", "")
                        characters = event_data.get("characters", [])
                        srt_start = event_data.get("srt_start")
                        srt_end = event_data.get("srt_end")

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
                        all_valid_events.append(event)
                    
                    last_end_idx = valid_slice_events[-1]["srt_end"]
                    current_start_idx = last_end_idx + 1
                    slice_success = True
                    logger.info(f"Progressive extraction: successfully saved {len(valid_slice_events)} events. Next start index: {current_start_idx}")
                    break
                else:
                    raise ValueError("No valid events could be parsed or validated from LLM response")

            except Exception as e:
                logger.warning(f"Error extracting events on attempt {attempt+1}/{max_retries} for index range [{current_start_idx}, {N-1}]: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed all {max_retries} attempts for index range [{current_start_idx}, {N-1}].")
                    break

        if not slice_success:
            logger.warning(f"Stopping progressive extraction due to consecutive failures at index {current_start_idx}")
            break

    logger.info(f"Progressive extraction finished. Extracted a total of {len(all_valid_events)} events for {episode_ref}")
    return all_valid_events