from pydantic import BaseModel
from typing import List, Dict
from json import JSONEncoder


class EntityLink(BaseModel):
    entity_name: str
    best_appellation: str
    appellations: List[str]
    presence_episodes: List[str] = []


class EntityLinkEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, EntityLink):
            return {
                "entity_name": obj.entity_name,
                "best_appellation": obj.best_appellation,
                "appellations": obj.appellations,
                "presence_episodes": obj.presence_episodes
            }
        return super().default(obj)


class ProcessedText(BaseModel):
    synopsis: str
    entities: List[EntityLink]
    semantic_segments: List[str]
    relationship_structure: List[Dict]