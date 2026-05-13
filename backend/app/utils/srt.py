import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SrtEntry:
    index: int
    start_time: str
    end_time: str
    content: str

def parse_srt(content: str) -> List[SrtEntry]:
    """Parse SRT file content into a list of SrtEntry."""
    # Pattern to match index, times, and content
    pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:(?!\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}).)*)', re.DOTALL)
    
    entries = []
    # Normalize line endings
    content = content.replace('\r\n', '\n').strip()
    
    # Split by double newline to handle typical SRT structure
    parts = re.split(r'\n\n+', content)
    
    for part in parts:
        match = pattern.match(part)
        if match:
            index = int(match.group(1))
            start_time = match.group(2)
            end_time = match.group(3)
            # Remove any HTML tags from content
            text = re.sub(r'<[^>]*>', '', match.group(4)).strip()
            entries.append(SrtEntry(index, start_time, end_time, text))
            
    return entries

def entries_to_text(entries: List[SrtEntry]) -> str:
    """Convert SRT entries to a simple text format with indices for LLM analysis."""
    return "\n".join([f"[{entry.index}] {entry.content}" for entry in entries])
