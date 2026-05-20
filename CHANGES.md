# Changes and Enhancements: ANTS Framework vs. previous Publication

This document outlines the differences between the current release of the **ANTS (Analysis of Narrative in Television Seriality)** framework and the initial implementation described in the publication:
> **Balestri, R. and Pescatore, G. (2025).** *Multi-Agent System for AI-Assisted Extraction of Narrative Arcs in TV Series*. In Proceedings of the 17th International Conference on Agents and Artificial Intelligence - Volume 1. DOI: [10.5220/0013369600003890](https://doi.org/10.5220/0013369600003890).

---

## 🔍 Overview of Transitions

The original implementation focused entirely on **text-based paratextual inputs** (preprocessed fan-Wiki summaries) to construct and analyze narrative arcs. The current version of ANTS transitions the system into a **multimodal narrative analysis cockpit**, enabling scholars to run analysis directly on **source video files**, generate automated transcripts, segment narrative events, and play back matched video clips.

### Feature Comparison Matrix

| Dimension | Previous Version | Current Version (ANTS) |
| :--- | :--- | :--- |
| **Primary Input Modality** | Text-only paratexts (simplified Wiki plots). | Multimodal (raw video, subtitle transcripts, and plots). |
| **Voice Transcription** | None (requires external transcription or paratexts). | **WhisperX** pipeline (automatic voice-to-text with word-level timestamps). |
| **Subtitle Synthesis** | None. | Automated `.srt` extraction and subtitle-to-plot synthesis. |
| **Narrative Event Segmentation** | None. | **Event-Driven Video Analysis** (automatic timeline event extraction). |
| **Video Processing** | None. | **FFmpeg Auto-Clipping Engine** (automatically extracts video clips for each narrative event). |
| **Visualization Dashboard** | Timeline, 3D PCA Vector clusters, character networks. | Extended Timeline, synchronized **Visual Video Player** showing event clips, andPCA Vector Explorer. |
| **Configuration** | Codebase editing / command line setup. | Fully integrated **Settings GUI** for live API/LLM key management. |
| **Deployment / Startup** | Manual installation and PATH setup. | Zero-configuration launchers (`setup.py`, `run_app.bat`, `run_app.sh`). |

---

## 🚀 Key Technical Enhancements

### 1. Automated Video Transcription & Plot Synthesis
The previous version relied on manual preprocessing (data cleaning, simplification, entity normalization) of wiki pages. The current version introduces:
* **WhisperX Integration:** Converts raw episode videos (`.mp4`, `.mkv`, etc.) into synchronized subtitle transcripts (`.srt`) with word-level alignments.
* **Subtitle-to-Plot Pipeline:** Synthesizes structured, linear chronological plot summaries (`.txt`) directly from the dialogue transcripts using LLMs, removing dependencies on external wiki paratexts.

### 2. Event-Driven Video Analysis & Auto-Clipping
This is a major architectural addition absent in the 2025 publication. Once narrative arcs are established, ANTS can:
* **Segment Events:** Use LLMs to scan dialogue and identify discrete storytelling beats (narrative events) with start/end time indicators.
* **Auto-Cut Clips:** Invoke wrapper commands around **FFmpeg/FFprobe** to segment and extract the corresponding video files into isolated playable clips automatically.
* **Arc-to-Event Mapping:** Map these short video clips to specific narrative arcs, allowing scholars to inspect the visual/dialogue representation of an arc directly.

### 3. Integrated Video Player & Dashboard Extensions
The user interface has been expanded from a static charting dashboard into an interactive video review workspace:
* **Annotated Video Player:** Scholars can inspect extracted narrative events, view their mapped narrative arcs, and play back the auto-extracted event video clips side-by-side in the web app.
* **Analysis Engine Panel:** Includes a batch checklist with real-time visual progress bars, allowing users to watch step-by-step progress during transcription, plot synthesis, multi-agent extraction, and event clipping.

### 4. Zero-Configuration Launchers
To facilitate ease of use for media scholars who do not have programming backgrounds:
* **Self-Configuring Environment:** Unified startup script detects the platform and automatically downloads precompiled `ffmpeg`/`ffprobe` binaries directly to `backend/bin/` if not present.
* **Settings GUI:** API endpoints, model choices, and API keys for OpenAI, Anthropic, Azure, and Cohere are configured through the in-app Settings panel, which writes directly to backend configuration stores.

---

## 🧠 Multi-Agent Framework Evolution: LangGraph & State Machine Orchestration

The previous implementation described in the paper also utilized LangGraph, but ran a linear sequence of **9 distinct agent nodes** (Existing Season Arcs Identifier, Anthology Arc Extractor, Soap & Genre-Specific Arc Extractor, Seasonal Arc Optimizer, Arc Deduplicator, Detail Enhancer, Progression Verifier, Character Role Verifier, and Final Reviewer). 

The new version optimizes this LangGraph StateGraph architecture by consolidating the 9 sequential steps into **3 main extraction nodes** followed by **4 specialized database/vector synchronization loop nodes**. This consolidation drastically reduces pipeline latency, token costs, and LLM context-switching.

### 1. Consolidated Sequential Extraction Nodes
Rather than making multiple sequential LLM calls across 9 individual nodes, the extraction phase is now grouped into highly optimized passes:
* `initialize_state_node`: Prepares the extraction context by loading character database models and presence logs directly from SQLModel/SQLite.
* `identify_present_season_arcs_node` (Matches **Agent 1**): Checks the synthesized transcript plot against existing non-anthology season arcs to determine narrative continuity.
* `extract_and_optimize_arcs_node` (Consolidates **Agents 2, 3, 4**): Performs a single comprehensive pass to extract anthology, soap, and genre-specific arcs while optimizing overlaps.
* `enhance_and_verify_arcs_node` (Consolidates **Agents 6, 7, 8, 9**): Validates character roles, shapes single-episode progression strings, and verifies consistency in a single verification pass.

### 2. Dynamic DB Synchronization & Deduplication Loop
In the previous prototype, deduplication occurred statically within a single agent block. The current system utilizes a dynamic state-machine loop that manages queue syncing and database merges:
* `search_candidates_node`: Uses **ChromaDB vector embeddings** (looking for cosine similarity distances $< 0.4$) alongside exact title matches in SQLite to search for existing candidate arcs.
* `deduplicate_arc_node` (Matches **Agent 5**): Runs a conditional state loop checking candidate matches one-by-one, querying the LLM for binary merge decisions (`same_arc` True/False).
* `evolve_metadata_node`: If matched, evolves the existing arc title and description over time based on the last 10 episodes of progression history.
* `persist_arc_node`: Writes the new arc, updates character links, and appends the progression entry, looping back for the next queued episode arc.

This state-machine architecture drastically reduces API tokens/costs, guarantees database model synchronization, and uses vector embedding search thresholds to keep the narrative deduplication process mathematically grounded.

---

## 💡 Addressing some of the Paper's Limitations

The current version of the software directly addresses some of the limitations mentioned in the paper. By utilizing **WhisperX transcripts** from the source video files and mapping narrative arcs to **FFmpeg-extracted video events**, the framework is bringing the scholar closer to the original text (the audiovisual series itself) rather than relying solely on user-edited fan paratexts.

