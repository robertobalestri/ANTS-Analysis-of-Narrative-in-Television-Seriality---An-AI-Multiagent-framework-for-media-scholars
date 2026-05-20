"""Video clip extraction service for temporal graph events."""
import os
from pathlib import Path
from typing import List, Optional
from app.models.narrative_event import NarrativeEvent
from app.services.processing.video_processing import extract_video_clip
from app.utils.srt import parse_srt
from app.core.logging import setup_logging

logger = setup_logging(__name__)


def srt_time_to_seconds(time_str: str) -> float:
    """
    Convert SRT timestamp (HH:MM:SS,mmm) to float seconds.
    """
    # Handle both comma and dot separators
    time_str = time_str.replace(',', ':').replace('.', ':')
    parts = time_str.split(':')
    if len(parts) != 4:
        raise ValueError(f"Invalid SRT timestamp format: {time_str}")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    millis = int(parts[3])

    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def seconds_to_srt_time(total_seconds: float) -> str:
    """
    Convert float seconds to SRT timestamp (HH:MM:SS,mmm).
    """
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    millis = int((total_seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def extract_event_clips(
    events: List[NarrativeEvent],
    video_path: str,
    output_dir: str,
    srt_content: Optional[str] = None
) -> List[NarrativeEvent]:
    """
    Extract video clips for each narrative event.

    Args:
        events: List of NarrativeEvent objects
        video_path: Path to the source video file
        output_dir: Directory to save extracted clips
        srt_content: Optional SRT content (if not provided, reads from standard location)

    Returns:
        List of NarrativeEvent objects with clip_path populated
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Parse SRT if not provided
    srt_entries = None
    if srt_content:
        from app.utils.srt import parse_srt
        srt_entries = parse_srt(srt_content)
    elif video_path:
        # Try to find SRT file in standard location
        video_dir = Path(video_path).parent
        srt_path = video_dir / (Path(video_path).stem + ".srt")
        if srt_path.exists():
            srt_entries = parse_srt(srt_path.read_text(encoding="utf-8"))

    updated_events = []
    for event in events:
        event_copy = NarrativeEvent.from_dict(event.to_dict())

        # Get timestamps from SRT entries if available
        if srt_entries and event.srt_start_index < len(srt_entries):
            srt_entry = srt_entries[event.srt_start_index]
            start_time = srt_entry.start_time
            if event.srt_end_index < len(srt_entries):
                end_time = srt_entries[event.srt_end_index].end_time
            else:
                end_time = srt_entries[-1].end_time

            # Calculate video timestamps
            event_copy.video_start = srt_time_to_seconds(start_time)
            event_copy.video_end = srt_time_to_seconds(end_time)
        else:
            # Use stored timestamps
            start_time = event.srt_start_time
            end_time = event.srt_end_time

        # Generate clip filename
        clip_filename = f"{event.id}.mp4"
        clip_path = output_path / clip_filename

        # Skip if clip already exists
        if clip_path.exists():
            logger.info(f"Clip already exists: {clip_path}")
            event_copy.clip_path = str(clip_path)
            updated_events.append(event_copy)
            continue

        # Extract clip
        success = extract_video_clip(
            input_video=video_path,
            output_clip=str(clip_path),
            start_time=start_time,
            end_time=end_time
        )

        if success:
            event_copy.clip_path = str(clip_path)
            logger.info(f"Extracted clip for event {event.id}: {clip_path}")
        else:
            logger.warning(f"Failed to extract clip for event {event.id}")

        updated_events.append(event_copy)

    return updated_events