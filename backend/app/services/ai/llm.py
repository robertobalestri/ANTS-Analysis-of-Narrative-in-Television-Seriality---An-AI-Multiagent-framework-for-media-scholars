"""LLM service for ANTS."""
import os
import time
from typing import List, Dict, Any, Optional
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai.models import get_llm
from app.core.logging import setup_logging
from app.utils.llm import clean_llm_json_response, clean_llm_text_response

logger = setup_logging(__name__)


class LLMService:
    """Service for LLM interactions with retry logic."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _retry_on_failure(self, func, *args, **kwargs):
        """Execute a function with retry logic."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after error: {e}")
        logger.error(f"All {self.max_retries} attempts failed")
        raise last_error

    def merge_identical_arcs(self, arcs: List[Dict[str, Any]], series: str) -> List[Dict[str, Any]]:
        """Decide which arcs should be merged based on similarity."""
        if len(arcs) <= 1:
            return arcs

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at analyzing narrative arcs in TV series."),
            ("human", """Given the following narrative arcs for series {series}, determine which ones should be merged because they represent the same overall story arc.
Return a JSON array of objects with 'arc_indices' (array of indices to merge) and 'merged_title' (combined title).
Only arcs that clearly represent the same overall story should be merged.

Arcs:
{arcs_json}

Return as a JSON array. If no merges needed, return empty array [].""")
        ])

        def _call():
            chain = prompt | self.llm
            response = chain.invoke({"series": series, "arcs_json": arcs})
            return clean_llm_json_response(response.content)

        return self._retry_on_failure(_call)

    def decide_arc_merging(
        self,
        new_arc: Any,
        existing_arc: Any,
    ) -> Dict[str, Any]:
        """Decide if two arcs should be merged, with confidence and reasoning."""
        arc1 = dict(new_arc) if hasattr(new_arc, '__dict__') and not isinstance(new_arc, dict) else new_arc
        arc2 = dict(existing_arc) if hasattr(existing_arc, '__dict__') and not isinstance(existing_arc, dict) else existing_arc

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at analyzing narrative arcs in TV series."),
            ("human", """Should these two narrative arcs be merged into one? 

Consider:
- Do they have the same overall story?
- Do they share main characters?
- Do they cover the same time period?

Arc 1: {arc1_title} - {arc1_description}
Arc 2: {arc2_title} - {arc2_description}

Return a JSON object with:
"same_arc": boolean,
"confidence": float (0.0 to 1.0),
"reasoning": string (brief explanation)""")
        ])

        def _call():
            chain = prompt | self.llm
            response = chain.invoke({
                "arc1_title": arc1.get("title"),
                "arc1_description": arc1.get("description"),
                "arc2_title": arc2.get("title"),
                "arc2_description": arc2.get("description"),
            })
            result = clean_llm_json_response(response.content)
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result if isinstance(result, dict) else {}

        return self._retry_on_failure(_call)

    def generate_progression_content(
        self,
        arc_title: str,
        arc_type: str,
        season: str,
        episode: str,
        previous_content: Optional[str] = None,
    ) -> str:
        """Generate content for an arc progression."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at summarizing TV series plot progressions."),
            ("human", """Generate a concise progression summary for the following narrative arc.

Arc: {arc_title} ({arc_type})
Season: {season}, Episode: {episode}

{previous_content_text}

Return a one paragraph summary.""")
        ])

        def _call():
            chain = prompt | self.llm
            response = chain.invoke({
                "arc_title": arc_title,
                "arc_type": arc_type,
                "season": season,
                "episode": episode,
                "previous_content_text": f"Previous: {previous_content}" if previous_content else "This is the first progression.",
            })
            return clean_llm_text_response(response.content)

        return self._retry_on_failure(_call)

    def resolve_character_appellation(
        self,
        character_name: str,
        series: str,
        known_appellations: List[str],
    ) -> str:
        """Resolve character name to the best existing appellation."""
        if not known_appellations:
            return character_name

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at analyzing character names in TV series."),
            ("human", """Given the character '{character_name}' in series {series}, and known appellations {known_appellations},
which is the best canonical name to use?

Return ONLY the best appellation.""")
        ])

        def _call():
            chain = prompt | self.llm
            response = chain.invoke({
                "character_name": character_name,
                "series": series,
                "known_appellations": known_appellations,
            })
            return clean_llm_text_response(response.content)

        return self._retry_on_failure(_call)

    def evolve_arc_metadata(
        self,
        current_title: str,
        current_description: str,
        progressions: List[str],
        new_progression: str,
    ) -> Dict[str, str]:
        """Evolve arc title and description based on progression history."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at maintaining the high-level identity of narrative arcs in TV series."),
            ("human", """As a TV series progresses, a narrative arc's title and overall description might need to evolve.
For example, a 'Secret Relationship' might just become a 'Relationship' once it's public knowledge.

Current Arc Title: {current_title}
Current Arc Description: {current_description}

Recent Progressions:
{progressions_text}

Latest Progression:
{new_progression}

Based on the cumulative story so far, provide an updated title and overall description for this arc. 
If the current title and description are still the most accurate summaries, return them unchanged.

Return as JSON with 'title' and 'description' keys.""")
        ])

        def _call():
            chain = prompt | self.llm
            progressions_text = "\n".join([f"- {p}" for p in progressions])
            response = chain.invoke({
                "current_title": current_title,
                "current_description": current_description,
                "progressions_text": progressions_text,
                "new_progression": new_progression,
            })
            result = clean_llm_json_response(response.content)
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result if isinstance(result, dict) else {}

        return self._retry_on_failure(_call)