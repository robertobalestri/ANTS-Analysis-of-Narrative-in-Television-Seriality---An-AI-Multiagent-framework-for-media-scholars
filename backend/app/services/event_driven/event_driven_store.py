"""Event-driven analysis store service using NetworkX."""
import os
import json
from pathlib import Path
from typing import List, Optional
import networkx as nx

from app.models.narrative_event import NarrativeEvent
from app.models.event_driven_analysis_snapshot import EventDrivenAnalysisSnapshot
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class EventDrivenStoreService:
    """In-memory event store using NetworkX for temporal narrative analysis."""

    def __init__(self, series: str, persist_directory: Optional[str] = None):
        self.series = series
        self.persist_directory = persist_directory or os.getenv("DATA_DIRECTORY", "./data")
        self.snapshot_file = Path(self.persist_directory) / series / "event_driven_analysis_snapshot.json"
        self._graph: Optional[nx.DiGraph] = None
        self._load_or_create()

    def _load_or_create(self) -> None:
        """Load existing event snapshot or create a new one."""
        if self.snapshot_file.exists():
            try:
                data = json.loads(self.snapshot_file.read_text(encoding="utf-8"))
                self._graph = self._deserialize_graph(data)
                logger.info(f"Loaded event store for series {self.series}: {len(self._graph.nodes)} events")
            except Exception as e:
                logger.warning(f"Failed to load event store, creating new: {e}")
                self._graph = nx.DiGraph()
        else:
            self._graph = nx.DiGraph()
            logger.info(f"Created new event store for series {self.series}")

    def _deserialize_graph(self, data: dict) -> nx.DiGraph:
        """Deserialize events from dict."""
        g = nx.DiGraph()
        for event_data in data.get("events", []):
            event = NarrativeEvent.from_dict(event_data)
            g.add_node(event.id, **event.to_dict())
        return g

    def _serialize_graph(self) -> dict:
        """Serialize events to dict."""
        events = []
        for node_id in self._graph.nodes:
            node_data = self._graph.nodes[node_id]
            events.append(node_data)
        return {
            "events": events,
            "active_terminal_nodes": self.get_active_terminals(),
        }

    def add_event(self, event: NarrativeEvent) -> None:
        """Add an event to the store."""
        self._graph.add_node(event.id, **event.to_dict())
        logger.debug(f"Added event {event.id} to store")

    def add_events(self, events: List[NarrativeEvent]) -> None:
        """Add multiple events to the store."""
        for event in events:
            self.add_event(event)

    def get_event(self, event_id: str) -> Optional[NarrativeEvent]:
        """Get an event by ID."""
        if event_id not in self._graph:
            return None
        data = self._graph.nodes[event_id]
        return NarrativeEvent.from_dict(data)

    def get_events(self) -> List[NarrativeEvent]:
        """Get all events."""
        events = []
        for node_id in self._graph.nodes:
            data = self._graph.nodes[node_id]
            events.append(NarrativeEvent.from_dict(data))
        return events

    def get_active_terminals(self) -> List[str]:
        """Get nodes with no outgoing edges (terminal events)."""
        return [n for n in self._graph.nodes if self._graph.out_degree(n) == 0]

    def get_subgraph(self, node_ids: List[str]) -> EventDrivenAnalysisSnapshot:
        """Get a snapshot subgraph containing only the specified nodes."""
        subgraph = self._graph.subgraph(node_ids)
        events = []
        for node_id in subgraph.nodes:
            data = subgraph.nodes[node_id]
            events.append(NarrativeEvent.from_dict(data))
        return EventDrivenAnalysisSnapshot(
            series=self.series,
            events=events,
            active_terminal_nodes=self.get_active_terminals(),
        )

    def find_paths(self, source_id: str, target_id: str) -> List[List[str]]:
        """Find all paths between two nodes."""
        try:
            return list(nx.all_simple_paths(self._graph, source_id, target_id))
        except nx.NetworkXNoPath:
            return []

    def get_snapshot(self) -> EventDrivenAnalysisSnapshot:
        """Get full event store snapshot."""
        return EventDrivenAnalysisSnapshot(
            series=self.series,
            events=self.get_events(),
            active_terminal_nodes=self.get_active_terminals(),
        )

    def serialize(self) -> dict:
        """Serialize store events to dict for persistence."""
        return self._serialize_graph()

    def deserialize(self, data: dict) -> None:
        """Load store events from dict."""
        self._graph = self._deserialize_graph(data)

    def save(self) -> None:
        """Save store events to JSON file."""
        self.snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        data = self._serialize_graph()
        self.snapshot_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved event snapshot for series {self.series}")

    def clear(self) -> None:
        """Clear the entire event store and delete persistence file."""
        self._graph = nx.DiGraph()
        if self.snapshot_file.exists():
            self.snapshot_file.unlink()
            logger.info(f"Deleted event snapshot file: {self.snapshot_file}")
        logger.info(f"Cleared event store for series {self.series}")