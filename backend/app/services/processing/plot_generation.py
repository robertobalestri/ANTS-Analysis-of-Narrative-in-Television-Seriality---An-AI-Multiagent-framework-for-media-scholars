from textwrap import dedent
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage
from app.core.logging import setup_logging
from app.utils.text import load_text
from app.utils.llm import clean_llm_text_response
import os

logger = setup_logging(__name__)

async def generate_plot_from_dialogues(dialogues_text: str, llm: ChatLiteLLM, output_path: str) -> str:
    """
    Generate a detailed plot summary from raw dialogues/subtitles.
    """
    prompt = dedent(f"""
    You are an expert narrative analyst. I will provide you with the full dialogues (subtitles) of a TV episode.
    Your task is to write a detailed, linear, and objective plot summary of the episode based ONLY on these dialogues.
    
    Guidelines:
    - Capture all key narrative events and character interactions.
    - Maintain a chronological order.
    - Focus on the 'what happens' rather than interpretation.
    - Do not include technical subtitle information (indices, timestamps).
    - Write in a professional, narrative style suitable for a media scholar's database.
    
    Dialogues:
    ---
    {dialogues_text}
    ---
    
    Detailed Plot Summary:
    """)

    try:
        # Split text if too long (very simple chunking for now if needed, but modern LLMs handle quite a bit)
        # For simplicity, we assume the LLM context is large enough for one episode's subtitles.
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        plot_summary = clean_llm_text_response(response.content.strip())

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(plot_summary)

        logger.info(f"Generated plot saved to {output_path}")
        return plot_summary
    except Exception as e:
        logger.error(f"Error generating plot from dialogues: {e}")
        raise
