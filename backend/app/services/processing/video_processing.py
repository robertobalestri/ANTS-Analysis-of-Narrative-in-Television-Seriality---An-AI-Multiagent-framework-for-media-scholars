import os
import subprocess
import logging
import json
import re
from typing import List, Dict, Any, Optional
from textwrap import dedent
from pathlib import Path

from app.core.logging import setup_logging
from app.services.ai import get_llm
from app.utils.srt import SrtEntry, parse_srt, entries_to_text
from langchain_core.messages import HumanMessage

logger = setup_logging(__name__)

async def map_segment_to_subtitles(segment_text: str, srt_entries: List[SrtEntry], llm: Any) -> Dict[str, Any]:
    """
    Use LLM to find the start and end subtitle indices that correspond to a semantic segment.
    """
    srt_text = entries_to_text(srt_entries)
    
    prompt = dedent(f"""
    I will provide you with a semantic segment from a plot summary and a list of numbered subtitles from the same episode.
    Your task is to identify the first and last subtitle indices that correspond to the actions and dialogue described in the plot segment.

    Plot Segment:
    ---
    {segment_text}
    ---

    Subtitles:
    ---
    {srt_text}
    ---

    Respond ONLY with a JSON object in the following format:
    {{
        "start_index": int,
        "end_index": int,
        "reasoning": "brief explanation of why these indices were chosen"
    }}
    """)

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw_content = response.content if hasattr(response, "content") else str(response)
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result
        else:
            logger.warning(f"Failed to parse LLM response for segment mapping: {raw_content}")
            return None
    except Exception as e:
        logger.error(f"Error mapping segment to subtitles: {e}")
        return None

def extract_video_clip(input_video: str, output_clip: str, start_time: str, end_time: str) -> bool:
    """
    Extract a video clip using FFmpeg.
    start_time and end_time are in SRT format (HH:MM:SS,mmm).
    """
    # Convert SRT timestamp to FFmpeg format (replace comma with dot or just use as is)
    # FFmpeg supports HH:MM:SS.ms
    start_ffmpeg = start_time.replace(',', '.')
    end_ffmpeg = end_time.replace(',', '.')
    
    # Calculate duration (FFmpeg -t expects duration, or we can use -to)
    # Using -to is easier as it specifies the end point.
    
    # We should use the ffmpeg binary from our bin folder
    ffmpeg_bin = "ffmpeg" # Default to PATH
    backend_dir = Path(__file__).resolve().parents[3]
    local_ffmpeg = backend_dir / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    
    if local_ffmpeg.exists():
        ffmpeg_bin = str(local_ffmpeg)

    try:
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", start_ffmpeg,
            "-to", end_ffmpeg,
            "-i", input_video,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            output_clip
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        if result.returncode == 0:
            logger.info(f"Successfully extracted clip: {output_clip}")
            return True
        else:
            logger.error(f"FFmpeg failed for {output_clip}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"FFmpeg execution error: {e}")
        return False
