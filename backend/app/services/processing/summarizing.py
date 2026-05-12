from textwrap import dedent
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage
from app.core.logging import setup_logging
from app.utils.text import load_text
from app.utils.llm import clean_llm_text_response
import os

logger = setup_logging(__name__)


async def summarize_plot(text: str, llm: ChatLiteLLM, output_path: str) -> str:
    prompt = dedent(f"""You are an expert at summarizing the main narrative arcs and plot progression of TV series.
    You will receive a plot description for a TV series and need to summarize it, focusing on the key narrative arcs and progression, while preserving the storyline without extraneous details.
    Your summary should be linear, capturing the primary events and shifts in the plot in a detailed, chronological manner without skipping around the text or adding commentary.
    Avoid conclusions or personal interpretation.
    Please summarize the following text:\n{text}""")

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    summary = clean_llm_text_response(response.content.strip())

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as output_file:
        output_file.write(summary)

    return summary