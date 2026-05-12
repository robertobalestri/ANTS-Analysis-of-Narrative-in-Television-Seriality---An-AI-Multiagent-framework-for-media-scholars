from langchain_core.prompts import ChatPromptTemplate
from textwrap import dedent

# ==============================
# Common Guidelines
# ==============================

NARRATIVE_ARC_GUIDELINES = dedent("""
**Guidelines for Narrative Arc Extraction**

1. **Arc Types:**
    - **Soap Arc**: Focuses on personal relationships (romance, family, friendships). Any love story qualifies.
    - **Genre-Specific Arc**: Pertains to the show's core genre elements (medical, political, professional conflicts) and spans multiple episodes.
    - **Anthology Arc**: Self-contained, single-episode stories driven by the show's genre.

2. **Title Creation:**
    - **Be Specific**: Titles must be clear and focused, including main characters if necessary.
    - **Avoid Vague Titles**: E.g., "Character X's Struggles", "Difficulties in the castle", "Difficulties in the workplace".
    - **Include Key Details**: Reference main characters and the central conflict/theme.

3. **Arc Description:**
    - **Long-Term Focus**: Do not describe the progression of the arc in the episode, but give an overview of the arc season-wide (unless it's an anthology arc).
    - **Overview**: Summarize what the arc is about (e.g., "Jane and Mark's romantic relationship").
    - **Avoid useless phrases**: E.g., "in this arc"

4. **Progression**: The progression should be specific to the arc in the episode, without speculations about what do the progressions mean for a character or other reasoning or research of meaning. Progressions should be precise key plot points separated by a dot.

5. **Character Lists:**
    - **Main Characters**: Protagonists driving the arc (typically two for relationship arcs). An arc should have at least one main character.
    - **Interfering Characters**: Characters that influence the arc within the episode (main characters or others)

6. **Arc Distinctness:**
    - **Clarity**: Each arc should be distinct without overlapping with others.
    - **Main Type**: Even if an arc is a little mix of soap and genre-specific type, choose the most appropriate type.

7. **Key Progression Points:**
    - **Major Events**: Identify turning points that advance the storyline or alter character dynamics during the specific episode.

**Example Breakdown:**
- **Arc Type**: Soap Arc
- **Title**: "Jane's Affair and Separation from Mark"
- **Description**: Jane's extramarital affair surfaces, causing tension with Mark and their children, leading to separation.
- **Main Characters**: Jane, Mark
- **Interfering Characters**: Karla, Bob, Julie
- **Progression**: The affair of Jane with her boss is revealed to Mark. Mark decides to separate from Jane. Karla, the judge, confirms the separation. The children, Bob and Julie, become distant.
8. **No Placeholders**: NEVER use generic descriptions or placeholders like "unnamed intern", "the patient", or "anonymous doctor" as character names. Only use specific names or clear identifiers.
""")

# ==============================
# Output Formats
# ==============================

DETAILED_OUTPUT_JSON_FORMAT = dedent("""
[
    {
        "title": "Specific Arc title. AVOID vague titles",
        "arc_type": "Soap Arc/Genre-Specific Arc/Anthology Arc",
        "description": "Brief season-wide description of the arc",
        "single_episode_progression_string": "Arc progression in this episode with key plot points.",
        "main_characters": "Character 1; Character 2; ...",
        "interfering_episode_characters": "Character 1; Character 2; ..."
    },
    ... more arcs ...
]
""")

EXTRACTOR_OUTPUT_JSON_FORMAT = dedent("""
[
    {
        "title": "Specific Arc title",
        "description": "Brief season-wide description of the arc",
        "arc_type": "Soap Arc/Genre-Specific Arc/Anthology Arc"
    },
    ... more arcs ...
]
""")

# ==============================
# Consolidated Prompt Templates
# ==============================

IDENTIFY_PRESENT_ARCS_PROMPT = ChatPromptTemplate.from_template(
    """You are a Season Arc Continuity Expert. Determine which of the known season arcs are present in this episode.

**Episode Plot:**
{episode_plot}

**Known Season Arcs:**
{season_arcs}

For each arc, determine if it continues or develops in this episode. An arc is present if specific events or character actions in the episode directly relate to it.

**Return a JSON array containing ONLY the arcs that are present in this episode:**
[
    {{
        "title": "Arc title (keep the original title exactly)",
        "description": "Arc description (keep the original description)",
        "explanation": "Brief explanation referencing specific events from the episode that show this arc is present"
    }},
    ... more present arcs ...
]

If no known arcs are present, return an empty array: []
"""
)

EXTRACT_AND_OPTIMIZE_ARCS_PROMPT = ChatPromptTemplate.from_template(
    """You are an Expert Narratologist. Analyze the episode plot and extract all narrative arcs in a single comprehensive pass.

**Episode Plot:**
{episode_plot}

**Already Known Season Arcs Present in This Episode:**
{present_season_arcs}

**Guidelines:**
{guidelines}

**Your Task — perform ALL of the following in one step:**

1. **Extract Anthology Arcs** (self-contained, case-of-the-week stories):
   - These must be self-contained within the episode and NOT part of a larger overarching arc.

2. **Extract Soap Arcs** (personal relationships, romances, family dynamics, friendships, personal growth):
   - Each arc must represent a specific, focused narrative thread.
   - Use specific titles including main characters.
   - If an arc matches an already known season arc, **keep its exact original title** and update the description if needed.

3. **Extract Genre-Specific Arcs** (professional conflicts, workplace dynamics, missions, power struggles, political maneuvers):
   - Must span or relate to multiple episodes (not episode-specific).
   - If an arc matches an already known season arc, **keep its exact original title** and update the description if needed.

4. **Deduplicate**: If two arcs describe the same storyline, merge them. Keep arcs separate if they focus on different aspects, involve different relationships, or cover different themes.

5. **Optimize Titles & Descriptions**: Ensure all titles are specific and all descriptions reflect the season-wide scope of the arc (not just this episode).

**Important Rules:**
- Be exhaustive: include ALL arcs representing meaningful relationship developments and narrative threads.
- Include every already known season arc that is present in the output, maintaining their original titles.
- Do NOT create arcs that overlap significantly with anthology arcs.
- Each arc must be distinct from all others.

**Return ALL arcs (anthology + soap + genre) as a single JSON array:**
{output_json_format}
"""
)

ENHANCE_AND_VERIFY_ARCS_PROMPT = ChatPromptTemplate.from_template(
    """You are an Expert Narratologist. For each arc below, add character details and episode progression, then verify everything is consistent.

**Episode Plot:**
{episode_plot}

**Arcs to Enhance and Verify:**
{arcs_to_process}

**Known Season Arcs Present in This Episode (for context):**
{present_season_arcs}

**Known Characters in the Episode (for reference):**
{known_characters}

**Guidelines:**
{guidelines}

**For EACH arc, you must:**

1. **Main Characters**: Identify the absolute protagonists driving this arc. For relationship arcs, include both parties. An arc must have at least one main character. Use names from the **Known Characters** list whenever possible.

2. **Interfering Episode Characters**: Identify characters who affect this arc in THIS specific episode. Use names from the **Known Characters** list. NEVER use generic placeholders like "unnamed intern".

3. **Single Episode Progression**: Write the key plot points for this arc in THIS episode:
   - Brief, focused statements separated by dots
   - ONLY events directly related to this arc's development
   - Simple present tense, active voice
   - No analysis, speculation, or character motivations
   - No phrases like "in this episode" or "we see that"

4. **Verify Consistency**:
   - Ensure the title is specific (not vague)
   - Ensure the description is season-wide (not episode-specific) unless it's an anthology arc
   - If the arc matches a known season arc, keep the original title
   - Ensure no two arcs overlap significantly

**Example Good Progression:**
"Jane discovers Mark's affair with his secretary. Mark moves out of the house. Their children choose to stay with Jane."

**Example Bad Progression:**
"In this episode, we see Jane struggling with her emotions when she finds out about Mark's affair, which leads to a confrontation where Mark decides to leave."

**Return ALL enhanced and verified arcs as a JSON array:**
{output_json_format}
"""
)

# Used by async processors for per-arc season continuity check
PRESENT_SEASON_ARCS_IDENTIFIER_PROMPT = ChatPromptTemplate.from_template(
    """You are a narrative continuity analyst. Determine if a known season arc appears in a specific episode.

**Episode Plot:**
{episode_plot}

**Known Season Arc:**
- Title: {arc_title}
- Description: {arc_description}

**Task:**
Determine if this arc continues or develops in the episode. Return a JSON object with:
- is_present: true/false
- title: exact original arc title
- description: exact original arc description
- explanation: brief explanation referencing specific events

Return ONLY a JSON object, no explanation or markdown.
"""
)