from app.core.logging import setup_logging
from typing import List
from langchain_litellm import ChatLiteLLM
import re
from langchain_core.messages import HumanMessage
from app.utils.text import split_into_sentences, clean_text
from app.utils.llm import clean_llm_text_response
from textwrap import dedent

logger = setup_logging(__name__)


def _preclean_raw_response(raw: str) -> str:
    """Fix char-by-char output before processing. LLM sometimes splits each character onto newlines."""
    if not raw:
        return raw
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    # If nearly all non-empty lines are single characters, collapse them
    if lines and len(lines) > 10 and sum(len(l) for l in lines) <= len(lines) * 3:
        return ''.join(lines)
    return raw


async def split_text(window_text: str, llm: ChatLiteLLM) -> List[str]:
    prompt = dedent(f"""
    Analyze the following text and insert <BOS> (Begin of Scene) tags only where a new semantic scene begins.
    If the text starts with an incomplete scene from a previous section, continue that scene and only add <BOS> tags for new scenes after it.

    Guidelines:
    - Scene shifts: A new scene usually starts when there is a major change in time or location, or a change of narrative or thematic focus during the same situation.
    - Dialogue continuity: Do not add a <BOS> tag if the scene remains the same during an ongoing conversation, unless there is a change in the focus of the discourse.
    - Minor transitions: Small movements within the same setting should not trigger a new scene tag unless the overall narrative shifts significantly.
    - Sentence integrity: Only place <BOS> tags at the beginning of sentences that introduce a new scene. Do not break sentences unnecessarily.
    - Event and Action focus: Only one major event or action usually happens per scene.
    - Thematic shifts: Continuous narration can consist of multiple scenes if the thematic focus substantially changes.
    - Time and Place words: Introductory words indicating time or place changes are potential indicators of a new scene. For example: "The next day", "Later", "In the forest", "On the way to...", "One day", "One evening", etc. might indicate a new scene.
    - Difference between anticipation and resolution: The anticipation of an event can be in one scene, and the resolution in another.
    - Structural words: Words like "Meanwhile", "Back at...", "Elsewhere..." are indicators of a scene shift.
    - Repetition: If a sentence repeats a previous idea (with slightly different wording), it's a sign of bad summarization and likely indicates the beginning of a new scene.

    Text to analyze:
    {window_text}

    Please return the text with <BOS> tags inserted only where significant narrative shifts occur. If the text starts with a continuation of a previous scene, do not add a <BOS> tag at the beginning.
    """)

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)
        marked_text = clean_llm_text_response(_preclean_raw_response(str(raw).strip()))

        segments = re.split(r'<BOS>', marked_text)
        segments = [clean_text(seg.strip()) for seg in segments if seg.strip()]

        return segments
    except Exception as e:
        logger.warning(f"split_text failed: {e}")
        return [window_text]


async def correct_segments(segments: List[str], llm: ChatLiteLLM, batch_size: int = 3) -> List[str]:
    logger.info("Starting segment correction")

    corrected_segments = []
    total = len(segments)

    for i in range(0, total, batch_size):
        batch = segments[i:i + batch_size]

        prompt = dedent(f"""
        Analyze the following segments and determine if they meet the criteria for valid semantic scenes. If any segment is invalid, please correct it by merging or splitting as necessary.

        Guidelines:
        - Scene shifts: A new scene usually starts when there is a major change in time or location, or a substantial change of narrative or thematic focus.
        - Dialogue continuity: The scene remains the same during an ongoing conversation, unless there is a substantial change in the focus of the discourse.
        - Minor transitions: Small movements within the same setting should not trigger a new scene unless the overall narrative shifts significantly.
        - Sentence integrity: Only split scenes at the beginning of sentences that introduce a new scene. Do not break sentences unnecessarily.
        - Event and Action focus: Only one major event or action usually happens per scene.
        - Thematic shifts: Continuous narration can consist of multiple scenes if the thematic focus substantially changes.
        - Time and Place words: Introductory words indicating time or place changes are potential indicators of a new scene. For example: "The next day", "Later", "In the forest", "On the way to...", "One day", "One evening", etc. might indicate a new scene.
        - Difference between anticipation and resolution: The anticipation of an event can be in one scene, and the resolution in another.

        Segments to analyze:
        {' '.join(f'<BOS> {seg}' for seg in batch)}

        Please return the corrected segments, each starting with <BOS>. If no corrections are needed, simply return the original segments.
        """)

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)
            corrected_text = clean_llm_text_response(_preclean_raw_response(str(raw).strip()))

            batch_corrected_segments = re.split(r'<BOS>', corrected_text)
            batch_corrected_segments = [clean_text(seg.strip()) for seg in batch_corrected_segments if seg.strip()]

            corrected_segments.extend(batch_corrected_segments)
            logger.info(f"Corrected batch {i // batch_size + 1}. Segments: {len(batch_corrected_segments)}")
        except Exception as e:
            logger.warning(f"correct_segments batch {i // batch_size + 1} failed: {e}")
            corrected_segments.extend(batch)

    logger.info(f"Segment correction complete. Total segments: {len(corrected_segments)}")
    return corrected_segments


async def semantic_split(text: str, llm: ChatLiteLLM, window_size: int = 20, correction_batch_size: int = 3) -> List[str]:
    """Split text into semantic scenes with correction pass."""
    logger.info("Starting semantic split")

    sentences = split_into_sentences(text)
    total_sentences = len(sentences)

    if total_sentences == 0:
        logger.warning("semantic_split received empty text, returning empty segments")
        return []

    sentences[0] = '<BOS> ' + sentences[0]

    initial_segments = []
    last_incomplete_segment = ""

    for i in range(0, total_sentences, window_size):
        window_end = min(i + window_size, total_sentences)
        window_text = last_incomplete_segment + ' ' + ' '.join(sentences[i:window_end])
        window_text = window_text.strip()

        logger.debug(f"Processing window: {i} to {window_end}")
        result = await split_text(window_text, llm)

        if result:
            if len(result) > 1:
                initial_segments.extend(result[:-1])
                last_incomplete_segment = result[-1]
            else:
                last_incomplete_segment = result[0]
        else:
            last_incomplete_segment += ' ' + window_text

        logger.info(f"Window processing complete. Segments: {len(result) if result else 0}")

    if last_incomplete_segment:
        initial_segments.append(last_incomplete_segment.strip())

    logger.info(f"Initial semantic split complete. Number of segments: {len(initial_segments)}")

    final_segments = await correct_segments(initial_segments, llm, correction_batch_size)

    logger.info(f"Semantic split and correction complete. Final number of segments: {len(final_segments)}")
    return final_segments