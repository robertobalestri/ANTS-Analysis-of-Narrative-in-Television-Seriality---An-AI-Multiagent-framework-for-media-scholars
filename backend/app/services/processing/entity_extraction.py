from app.core.logging import setup_logging
from typing import List
from collections import defaultdict
import json
import re
import os
from textwrap import dedent
from langchain_core.messages import HumanMessage
from langchain_litellm import ChatLiteLLM
from app.utils.llm import clean_llm_json_response
from app.models.processing import EntityLink
from app.repositories import DatabaseSessionManager, CharacterRepository
from app.services.narrative import CharacterService

logger = setup_logging(__name__)


async def _extract_entities_with_llm(
    plot: str,
    llm: ChatLiteLLM,
    existing_entities: List[EntityLink],
) -> List[EntityLink]:
    """
    Extract characters from the plot using a language model with detailed instructions.
    """
    existing_info = "Existing characters in the series (for reference):\n" + "\n".join(
        [f"- {e.best_appellation} ({e.entity_name})" for e in existing_entities]
    )

    prompt = dedent(f"""
        You are an expert in narrative analysis. Extract all characters mentioned in the following plot.

        **Plot:**
        {plot}

        **{existing_info}**

        **Instructions:**
        1. Identify EVERY character mentioned in the plot.
        2. For each character, decide if they match one of the "Existing characters" listed above.
        3. If it's an existing character, use their exact `entity_name`.
        4. If it's a new character, create a primary name in the format "name_surname" (lowercase with underscores).
        5. For groups or families, use "the_surname" format.
        6. List ONLY stable, proper appellations in the `appellations` list:
           - ALLOWED: Full names (Derek Shepherd), First names (Derek), and specific, stable nicknames (The Chief, 007).
           - ALLOWED POSSESSIVES: Only those containing a proper name (e.g., "Meredith's mother", "Tony's wife").
           - EXCEPTION FOR TITLED NAMES: If a character is primarily identified by "Title + Surname" (e.g., "Mr. Jones", "Mr. Tudor"), treat that exact combination as a valid appellation. However, NEVER include the lonely surname (e.g., "Jones") by itself.
           - FORBIDDEN: Lonely Surnames (e.g., do not include "Grey" or "Shepherd" alone).
           - FORBIDDEN: Professional/Social Titles (Dr., Nurse, Chief, etc.) when they accompany a full name or are used as generic labels.
           - FORBIDDEN: Generic descriptions (the man, the woman, the patient, the intern, the nurse, another intern).
           - FORBIDDEN: Pronoun-based relationships (her mother, his parents, their son, her one-night stand).
           - FORBIDDEN: Transient states (the sleeping Miranda Bailey, the crying girl).
        7. Choose the `best_appellation` (display name): ALWAYS use "Name Surname" format if known. If only "Title + Surname" is known (e.g., "Mr. Jones"), use that exact combination. NEVER include titles like "Dr." or "Nurse" for characters with known full names.
        8. Exclude non-character entities (locations, companies, objects, or abstract entities like "God").

        **Return a JSON list of objects:**
        [
            {{
                "entity_name": "primary_name",
                "best_appellation": "Chosen Appellation",
                "appellations": ["Appellation1", "Appellation2", ...]
            }},
            ...
        ]
        """)

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)
        entities_data = clean_llm_json_response(raw)
        logger.info(f"LLM extracted entities: {entities_data}")

        if isinstance(entities_data, list):
            # Ensure best appellation is included in the appellations list
            for entity in entities_data:
                best_appellation = entity.get("best_appellation")
                if best_appellation and best_appellation not in entity.get("appellations", []):
                    entity["appellations"].append(best_appellation)
            return [EntityLink(**item) for item in entities_data]
        else:
            logger.error(f"Unexpected format for extracted entities: {entities_data}")
            return []
    except Exception as e:
        logger.error(f"Failed to extract entities with LLM: {e}")
        return []


async def resolve_duplicate_entities(
    existing_entities: List[EntityLink],
    refined_entities: List[EntityLink],
    plot: str,
    llm: ChatLiteLLM,
) -> List[EntityLink]:
    """
    Resolve duplicate entities that share the same appellation by consulting the language model.
    """
    # Create a mapping of entity_name to EntityLink for quick lookup
    entity_map = {
        entity.entity_name: entity
        for entity in existing_entities + refined_entities
    }

    # Create a mapping of appellations to entity_names
    appellation_map: dict = defaultdict(set)
    for entity in entity_map.values():
        for appellation in entity.appellations:
            appellation_map[appellation].add(entity.entity_name)

    # Track which entities have been merged
    merged_pairs: set = set()

    for appellation, entity_names in appellation_map.items():
        if len(entity_names) > 1:
            entity_names = sorted(entity_names)  # Sort for consistent processing

            for i, name1 in enumerate(entity_names):
                for name2 in entity_names[i + 1:]:
                    # Skip if this pair has already been processed
                    if (name1, name2) in merged_pairs:
                        continue

                    entity1 = entity_map[name1]
                    entity2 = entity_map[name2]

                    prompt = dedent(f"""There are multiple entities sharing the same appellation "{appellation}":
                    Entity 1: {entity1.entity_name} (appellations: {', '.join(entity1.appellations)})
                    Entity 2: {entity2.entity_name} (appellations: {', '.join(entity2.appellations)})
                    Based on the following plot context, should these be treated as separate entities or merged into one?
                    Plot: {plot}
                    Please provide a clear answer: "separate" or "merge".
                    """)

                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    decision = response.content.strip().lower()
                    logger.info(f"LLM decision for {appellation} between {name1} and {name2}: {decision}")

                    if decision == "merge":
                        # Create merged entity
                        merged_appellations = list(set(entity1.appellations + entity2.appellations))
                        merged_entity = EntityLink(
                            entity_name=entity1.entity_name,  # Keep the first entity's name
                            best_appellation=entity1.best_appellation,
                            appellations=merged_appellations,
                            presence_episodes=entity1.presence_episodes,
                        )
                        entity_map[entity1.entity_name] = merged_entity
                        entity_map[entity2.entity_name] = merged_entity  # Point both to same entity
                        merged_pairs.add((name1, name2))

                    # Mark as processed regardless of decision
                    merged_pairs.add((name1, name2))

    # Collect final unique entities that were actually present in the current plot
    present_in_plot_names = {e.entity_name for e in refined_entities}
    processed_names: set = set()
    final_entities: list = []

    for name in present_in_plot_names:
        entity = entity_map[name]
        if entity.entity_name not in processed_names:
            final_entities.append(entity)
            processed_names.add(entity.entity_name)

    return final_entities


def substitute_appellations_with_names(
    text: str,
    entities: List[EntityLink],
) -> str:
    """
    Substitute all appellations in the text with their corresponding best appellations.
    Sorts appellations by length to handle longer ones first. Uses word boundary regex.
    """
    if not entities:
        return text

    # Collect all (appellation, best_appellation) pairs
    replacements = []
    for entity in entities:
        for appellation in entity.appellations:
            if appellation != entity.best_appellation:
                replacements.append((appellation, entity.best_appellation))

    # Sort replacements by appellation length (longest first) to avoid partial replacements
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    # Create a copy of the text to modify
    modified_text = text

    for appellation, best_name in replacements:
        if len(appellation.strip()) > 1:  # Skip empty or single-char names
            # Use regex with word boundaries to replace only whole words
            pattern = r'\b' + re.escape(appellation) + r'\b'
            modified_text = re.sub(pattern, best_name, modified_text)

    return modified_text


async def extract_and_refine_entities(
    plot: str,
    llm: ChatLiteLLM,
    series: str,
    season: str,
    episode_code: str,
) -> List[EntityLink]:
    """
    Extract and refine entities from the plot in a single pass.
    Loads existing entities from season JSON, runs extraction + duplicate resolution,
    syncs to DB via CharacterService, updates season JSON, and returns refined entities.
    """
    # Step 1: Load existing entities from season_entities_path
    from app.services.filesystem.path_handler import PathHandler
    base_dir = os.environ.get("DATA_DIR", "data")
    path_handler = PathHandler(series, season, "E01", base_dir=base_dir)
    season_entities_path = path_handler.get_season_extracted_refined_entities_path()

    existing_entities: List[EntityLink] = []
    if os.path.exists(season_entities_path):
        try:
            with open(season_entities_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            existing_entities = [
                EntityLink(
                    entity_name=item.get("entity_name", ""),
                    best_appellation=item.get("best_appellation", item.get("entity_name", "")),
                    appellations=item.get("appellations", []),
                    presence_episodes=item.get("presence_episodes", []),
                )
                for item in data
            ]
            logger.info(f"Loaded {len(existing_entities)} existing entities from season file")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load existing entities from {season_entities_path}: {e}")
            existing_entities = []

    # Step 2: Extract entities with detailed prompt (single LLM call)
    refined_entities = await _extract_entities_with_llm(plot, llm, existing_entities)

    # Step 3: Resolve duplicates
    refined_entities = await resolve_duplicate_entities(existing_entities, refined_entities, plot, llm)

    # Step 4: Sync to DB via CharacterService
    db_manager = DatabaseSessionManager()
    with db_manager.session_scope() as session:
        character_repository = CharacterRepository(session)
        character_service = CharacterService(character_repository)

        for entity in refined_entities:
            character_service.add_or_update_character(
                entity.entity_name,
                entity.best_appellation,
                entity.appellations,
                series,
                episode_code,
            )

    # Step 5: Update season entities JSON file
    all_entities: dict = {entity.entity_name: entity for entity in existing_entities}
    for entity in refined_entities:
        if entity.entity_name in all_entities:
            existing_ent = all_entities[entity.entity_name]
            # Merge presence episodes
            existing_episodes = set(existing_ent.presence_episodes)
            existing_episodes.update(entity.presence_episodes)
            entity.presence_episodes = sorted(list(existing_episodes))
            # Merge appellations
            existing_apps = set(existing_ent.appellations)
            existing_apps.update(entity.appellations)
            entity.appellations = list(existing_apps)
        all_entities[entity.entity_name] = entity

    os.makedirs(os.path.dirname(season_entities_path), exist_ok=True)
    with open(season_entities_path, "w", encoding="utf-8") as f:
        json.dump([ent.model_dump() for ent in all_entities.values()], f, indent=2, ensure_ascii=False)

    # Step 6: Return refined entities
    return refined_entities


# Keep these for backwards compatibility / direct usage
def load_existing_entities(series: str, season: str, base_dir: str = "data") -> List[EntityLink]:
    from app.services.filesystem.path_handler import PathHandler
    path_handler = PathHandler(series, season, "E01", base_dir=base_dir)
    season_entities_path = path_handler.get_season_extracted_refined_entities_path()

    try:
        with open(season_entities_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entities = []
        for item in data:
            entities.append(EntityLink(
                entity_name=item.get("entity_name", ""),
                best_appellation=item.get("best_appellation", item.get("entity_name", "")),
                appellations=item.get("appellations", []),
                presence_episodes=item.get("presence_episodes", []),
            ))
        return entities
    except (OSError, json.JSONDecodeError):
        return []


def load_existing_entities_from_db(series: str) -> List[EntityLink]:
    db_manager = DatabaseSessionManager()
    entities = []

    with db_manager.session_scope() as session:
        character_repo = CharacterRepository(session)
        characters = character_repo.get_by_series(series)

        for char in characters:
            appellations = [a.appellation for a in char.appellations] if char.appellations else [char.entity_name]
            entities.append(EntityLink(
                entity_name=char.entity_name,
                best_appellation=appellations[0] if appellations else char.entity_name,
                appellations=appellations,
                presence_episodes=[],
            ))

    return entities


def update_season_entities(
    series: str,
    season: str,
    episode_code: str,
    extracted_entities: List[EntityLink],
    base_dir: str = "data",
) -> None:
    from app.services.filesystem.path_handler import PathHandler
    path_handler = PathHandler(series, season, "E01", base_dir=base_dir)
    season_entities_path = path_handler.get_season_extracted_refined_entities_path()

    # Load existing entities
    existing = []
    if os.path.exists(season_entities_path):
        with open(season_entities_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # Convert to EntityLink dicts by entity_name
    existing_by_name = {e["entity_name"]: e for e in existing}

    for entity in extracted_entities:
        if entity.entity_name in existing_by_name:
            # Update appellations and presence
            existing_ent = existing_by_name[entity.entity_name]
            for app in entity.appellations:
                if app not in existing_ent["appellations"]:
                    existing_ent["appellations"].append(app)
            if episode_code not in existing_ent["presence_episodes"]:
                existing_ent["presence_episodes"].append(episode_code)
        else:
            existing_by_name[entity.entity_name] = {
                "entity_name": entity.entity_name,
                "best_appellation": entity.best_appellation,
                "appellations": entity.appellations,
                "presence_episodes": [episode_code],
            }

    os.makedirs(os.path.dirname(season_entities_path), exist_ok=True)
    with open(season_entities_path, "w", encoding="utf-8") as f:
        json.dump(list(existing_by_name.values()), f, indent=2, ensure_ascii=False)