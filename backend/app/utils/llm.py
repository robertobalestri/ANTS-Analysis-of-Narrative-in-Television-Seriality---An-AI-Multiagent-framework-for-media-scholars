"""LLM response parsing utilities."""
import json
import re
from typing import Dict, List

from app.core.logging import setup_logging

logger = setup_logging(__name__)


def clean_llm_json_response(response: str) -> List[Dict]:
    """Clean and extract a valid JSON array from the LLM response."""
    response_cleaned = re.sub(r"```(json|plaintext|markdown)?", "", response)
    response_cleaned = re.sub(r'//.*?$|/\*.*?\*/', '', response_cleaned, flags=re.MULTILINE | re.DOTALL)
    json_match = re.search(r'(\{|\[)[\s\S]*(\}|\])', response_cleaned)

    if response_cleaned[0] in ['"', "'"]:
        response_cleaned = response_cleaned[1:]
    if response_cleaned[-1] in ['"', "'"]:
        response_cleaned = response_cleaned[:-1]

    if json_match:
        json_str = json_match.group(0)
        json_str = json_str.replace("'", "'")

        if json_str.startswith('{'):
            json_str = f'[{json_str}]'

        try:
            parsed_json = json.loads(json_str)
            if isinstance(parsed_json, dict):
                return [parsed_json]
            elif isinstance(parsed_json, list):
                return parsed_json
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cleaned JSON: {e}")
            logger.error(f"Cleaned JSON string: {json_str}")
            logger.error(f"Full response: {response}")
            raise ValueError(f"Failed to parse cleaned JSON: {e}")

    raise ValueError("No valid JSON object or array found in the response")


def clean_llm_text_response(response: str) -> str:
    """Clean and extract meaningful text from a markdown or plaintext LLM response."""
    response_cleaned = re.sub(r"```(plaintext|markdown|html)?", "", response)
    response_cleaned = re.sub(r"```", "", response_cleaned)
    response_cleaned = re.sub(r"'", "'", response_cleaned)

    # Detect and fix character-by-character output (LLM sometimes splits each char on newlines)
    lines = response_cleaned.split('\n')
    merged_lines = []
    buffer = ""
    for line in lines:
        stripped = line.strip()
        # If line is a single character (including punctuation), accumulate into buffer
        if len(stripped) == 1:
            buffer += stripped
        else:
            if buffer:
                merged_lines.append(buffer)
                buffer = ""
            merged_lines.append(line.rstrip())
    if buffer:
        merged_lines.append(buffer)

    response_cleaned = '\n'.join(merged_lines)
    response_cleaned = response_cleaned.strip()
    return response_cleaned