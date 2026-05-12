"""Text utilities for ANTS."""
import json
import os
import re
from typing import Dict, List


def load_text(file_path: str) -> str:
    """Load text from file with encoding fallback."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1252') as f:
            return f.read()


def load_json(file_path: str) -> List[Dict]:
    """Load JSON from file with encoding fallback."""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1252') as f:
            return json.load(f)


def clean_text(text: str) -> str:
    """Preprocess input text by removing extra whitespace and normalizing line breaks."""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def save_json(data: dict, file_path: str) -> None:
    """Save JSON to file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# NLTK sentence tokenization
import nltk
from nltk.tokenize import sent_tokenize


def _ensure_nltk_resources():
    """Ensure NLTK resources are available."""
    try:
        sent_tokenize("test")
    except LookupError:
        nltk.download('punkt')
        nltk.download('punkt_tab')


_ensure_nltk_resources()


def split_into_sentences(text: str) -> List[str]:
    """Split input text into sentences."""
    return sent_tokenize(text)