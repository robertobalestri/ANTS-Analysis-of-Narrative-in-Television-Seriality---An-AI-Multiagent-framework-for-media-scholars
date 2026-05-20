<p align="center">
  <img src="assets/ants%20logo.png" width="600" alt="ANTS Logo">
</p>

# ANTS: Analysis of Narrative in Television Seriality

**ANTS** is an advanced AI-powered framework designed specifically for media scholars and narrative analysts. It provides a comprehensive suite of tools for extracting, analyzing, and visualizing complex narrative structures in long-form television content.

> **Note on Research Heritage:**  
> This work is an extension and enhancement of the original research described in:  
> **Balestri, R. and Pescatore, G. (2025).** *Multi-Agent System for AI-Assisted Extraction of Narrative Arcs in TV Series*. In Proceedings of the 17th International Conference on Agents and Artificial Intelligence - Volume 1. DOI: [10.5220/0013369600003890](https://doi.org/10.5220/0013369600003890).  
> 
> A comprehensive comparison of the new features, pipeline extensions, and multi-agent graph optimizations is readable in [CHANGES.md](CHANGES.md). The repository for the earlier, text-only prototype implementation is archived at [robertobalestri/MAS-AI-Assisted-Narrative-Arcs-Extraction-TV-Series](https://github.com/robertobalestri/MAS-AI-Assisted-Narrative-Arcs-Extraction-TV-Series).

---

## 📌 Table of Contents
1. [Core Features](#-core-features)
2. [UI & Workspace Navigation](#-ui--workspace-navigation)
3. [Quick Start](#-quick-start)
4. [Environment Configuration](#-environment-configuration)
5. [Required Files for Analysis & Generation Pipelines](#-required-files-for-analysis--generation-pipelines)
6. [Recommended End-to-End Workflow](#-recommended-end-to-end-workflow)

---

## 🚀 Core Features

### 🏛️ Library & Metadata Management
* **Hierarchical Organization:** Manage research targets seamlessly by Series, Seasons, and Episodes.
* **Flexible Ingestion Pipelines:** Ingest narrative data via direct upload (plots, subtitles, videos), or utilize automated transcription pipelines and AI starting from the video file only.

### 🧠 Multi-Agent Narrative Arc Extraction
* **Narrative Arc Extraction:** Map and track story threads across multiple episodes using orchestrated multi-agent workflows.

### 🎬 Event-Driven Video Analysis
* **Narrative Event Extraction:** Scans transcripts via LLM to identify distinct narrative events.
* **Auto-Clipping Engine:** Automatically segments and extracts individual video clips for each narrative event.
* **Arc-to-Event Mapping:** Links narrative arcs to single events to build a comprehensive understanding of the narrative structure.

### 📊 Comprehensive Visualization Dashboards

#### Narrative Arcs Dashboard

* **Interactive Timeline:** High-fidelity tracking of narrative arcs and their evolution across episodes.
* **Vector Store Explorer:** Interactive 3D PCA visualization of narrative arc clusters to discover hidden semantic relations.
* **Characters:** Look at all the characters present in the show.

#### Event Driven Video Analysis Dashboard

* **Video Player:** Play back auto-extracted event clips.
* **Arc-to-Event Mapping:** Links narrative arcs to single events to build a comprehensive understanding of the narrative structure.

---

## 🧭 UI & Workspace Navigation

The sidebar acts as the primary cockpit for the framework:

### 1. Active Panels
* **Series Manager & File Upload:** The ingestion workspace for library curation and text synthesis.
* **Analysis Engine:** The control center for executing multi-agent background workers.
* **Narrative Arcs Dashboard:** The visualization platform subdivided into *Timeline*, *Vector Store*, and *Characters*.
* **Event Driven Video Analysis Dashboard:** The interface for inspecting timestamped narrative events and reviewing clipped video clips.
* **Settings:** Live management UI for LLM providers and API keys.

### 2. Global Workspace Controls
* **Add Series Form:** Quickly initialize a new dataset folder structure by specifying a short code and display name.
* **Library Switcher:** Toggle instantly between active series profiles, updating the workspace target dynamically across all views.

---

## ⚙️ Quick Start

The fastest way to launch **ANTS** is by using the unified startup script, which automatically configures both your local environment and required binaries.

### 1. Prerequisites
* **Python 3.10+**

### 2. Launching the Framework
1. Clone the repository and navigate to the project root folder.
2. Run the automated startup script matching your operating system:
   * **Windows:** Double-click `run_app.bat` or run:
     ```cmd
     run_app.bat
     ```
   * **macOS / Linux:** Run the shell script:
     ```bash
     ./run_app.sh
     ```
3. The script will dynamically orchestrate the following:
   * Build a Python virtual environment (`.venv`) and install dependencies.
   * Detect your operating system and automatically download the correct local `ffmpeg`/`ffprobe` binaries inside `backend/bin/` if not already present.
   * Start the backend server and serve the pre-built frontend interface.
   * Launch the application directly in your default browser at `http://localhost:8000`.

### 3. Core Configuration
1. Open the **Settings** panel from the sidebar inside the app web UI.
2. Input your preferred LLM provider configurations (OpenAI, Azure, Anthropic, Ollama, etc.) and credentials.
3. Save settings. This automatically creates and updates your secure `backend/.env` file.

---

## 🔑 Environment Configuration

The framework manages variables dynamically via the **Settings UI**.

### Core LLM & Embedding Layer

| Variable | Description |
| --- | --- |
| **LLM_API_KEY** | Authentication key for your chosen language model provider. |
| **LLM_API_BASE** | Target endpoint URL for the API provider. |
| **LLM_MODEL** | Identification string for the model (e.g., `gpt-5.5`, `claude-4.5-sonnet`). |
| **EMBED_API_KEY** | Authentication key for the vector embedding provider. |
| **EMBED_API_BASE** | Target endpoint URL for the embedding provider. |
| **EMBED_MODEL** | Embedding Model configuration string for text vectorization (e.g., `bge-large-en-v1.5`, `text-embedding-3-small`). |

### Advanced Engine Parameters

| Variable | Default Value | Description |
| --- | --- | --- |
| **LLM_PROVIDER** | `""` | Provider engine string (`openai`, `azure`, `anthropic`, `ollama`). It is needed, for example, for Microsoft Azure inferencing endpoints. |
| **EMBED_PROVIDER** | `"openai"` | Embedding engine string (`openai`, `azure`, `cohere`). |


---

## 📋 Required Files for Analysis & Generation Pipelines

To run different types of narrative processing and analysis, ensure the correct source files are present in the episode directory. The dashboard indicates file presence with checkmarks/crosses.

| Pipeline / Analysis Operation | Required Input Files | Output / Resulting Files | Description |
| :--- | :--- | :--- | :--- |
| **Subtitle-to-Plot Synthesis** | Subtitle file (`.srt`) | Plot summary (`.txt`) | Uses LLMs to summarize dialog transcripts into a linear, chronological plot summary. |
| **Video Transcription** | Video file (`.mp4`, `.mkv`, etc.) | Subtitle file (`.srt`) | Uses WhisperX to transcribe voice tracks with word-level timestamps. |
| **Full Video-to-Plot Pipeline** | Video file (`.mp4`, `.mkv`, etc.) | Subtitle (`.srt`) & Plot (`.txt`) | Runs video transcription, then synthesizes the plot summary in one unified execution. |
| **Narrative Arc Extraction** | Plot summary (`.txt`) | SQLite & ChromaDB Vector Store artifacts | Orchestrates multi-agent analysis to extract story arcs, character profiles, and vector embeddings. |
| **Event-Driven Video Analysis** | Video file, Subtitle file (`.srt`), **AND** Completed Narrative Arc Extraction | Mapped events & Auto-clipped video clips | Scans transcripts, slices narrative events into individual video clips via FFmpeg, and maps them to known arcs. |

---

## 🏆 Recommended End-to-End Workflow

For the easiest onboarding experience when starting with a new series, follow this step-by-step pipeline:

1. **Set API Keys:** Open the **Settings** panel from the sidebar and input your LLM provider credentials.
2. **Initialize Series:** Use the **Add Series Form** at the bottom of the sidebar to create a new series profile.
3. **Populate Seasons & Episodes:** Navigate to the **Series Manager** and create your target seasons and episodes.
4. **Upload Videos:** Upload the video files (`.mp4`, `.mkv`, etc.) for each episode under the **Series Manager** upload area.
5. **Batch Generate Support Files:** Go to the **Analysis Engine** from the sidebar, select all episodes in the checklist, and click **Generate Missing Files**.
   > **Important:** *Transcription and plot generation runs neural speech-to-text models (WhisperX) and LLM extraction, which can take a significant amount of time depending on hardware speed (GPU/CPU) and video length.*
6. **Scholar Review & Correction:** Because LLM-generated plot summaries serve as the foundational source material for subsequent analysis, scholars should always review the generated plots from the **Series Manager** and make manual corrections directly in the UI before proceeding.
7. **Extract Narrative Arcs:** Once the plot files are ready, select all episodes in the **Analysis Engine** and click **Start Narrative Arc**.
8. **Explore & Correct Arcs:** Use the **Narrative Arcs Dashboard** to explore the extracted narrative arcs. You can merge, add, delete, and modify the arcs directly.
   > **Important:** *It is highly recommended to correct and stabilize your narrative arcs before proceeding to event-driven video mapping.*
9. **Perform Event-Driven Video Analysis:** After narrative arcs are finalized, go back to the **Analysis Engine**, select your episodes, and click **Start Event Driven** to generate timestamped video clips and arc-to-event mappings.
10. **Explore & Visualize Final Results:** Use the **Event-Driven Video Analysis Dashboard** to explore the extracted narrative events and review their automated video clips side-by-side with your narrative arcs.

---

*Created by media scholars, for media scholars.*