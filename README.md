<p align="center">
  <img src="assets/ants%20logo.png" width="600" alt="ANTS Logo">
</p>

# ANTS: Analysis of Narrative in Television Seriality

**ANTS** is an advanced AI-powered framework designed specifically for media scholars and narrative analysts. It provides a comprehensive suite of tools for extracting, analyzing, and visualizing complex narrative structures in long-form television content.

---

## 📌 Table of Contents
1. [Core Features](#-core-features)
2. [How It Works (Step-by-Step Workflow)](#-how-it-works-step-by-step-workflow)
3. [UI & Workspace Navigation](#-ui--workspace-navigation)
4. [Quick Start](#-quick-start)
5. [Developer Setup & Architecture](#-developer-setup--architecture)
6. [Environment Configuration](#-environment-configuration)

---

## 🚀 Core Features

### 🏛️ Library & Metadata Management
* **Automated Series Ingestion:** Create series with just a code and name; pulls official posters and metadata via the IMDb API.
* **Hierarchical Organization:** Manage research targets seamlessly by Series, Seasons, and Episodes.
* **Flexible Ingestion Pipelines:** Ingest narrative data via direct upload (plots, subtitles, videos), or utilize automated transcription pipelines and AI starting from the video file only.

### 🧠 Multi-Agent Analysis Engine
* **Narrative Arc Extraction:** Map and track overlapping story threads across multiple episodes using orchestrated multi-agent workflows.
* **Character Profiling:** Automatically extract, resolve, and stabilize character identities over long-form seriality.

### 🎬 Event-Driven Video Analysis
* **Narrative Event Extraction:** Scans transcripts via LLM to identify narrative events.
* **Auto-Clipping Engine:** Automatically segments and extracts individual video clips for each narrative event.
* **Arc-to-Event Mapping:** Links narrative arcs to single events to build a comprehensive understanding of the narrative structure.

### 📊 Visualization Dashboard of Narrative Arc Extraction
* **Interactive Timeline:** High-fidelity tracking of narrative arcs and their presence across episodes.
* **Vector Store Explorer:** Interactive 3D PCA visualization of narrative beat clusters to discover hidden semantic relations.
* **Character Networks:** Track character appearances, prominence, and interactive roles.
* **Annotated Video Player:** Play back auto-extracted event clips directly alongside their multi-agent narrative annotations.

### 📊 Visualization Dashboard of Event-Driven Video Analysis
* **Interactive Timeline:** High-fidelity tracking of events and how they relate to narrative arcs.
* **Annotated Video Player:** Play back auto-extracted event clips directly.


---

## 📖 How It Works (Step-by-Step Workflow)

### Step 1: Ingest & Populate Media Assets
Navigate to the **Series Manager**. Initialize your target series (e.g., Code: `B99`, Name: `Brooklyn Nine-Nine`). You can populate an episode's source materials using four methodologies depending on available assets:
* **Direct Upload:** Drag-and-drop pre-existing written plot summaries (`.txt`), subtitle transcripts (`.srt`), or video files.
* **Subtitle-Only Ingestion:** Upload an `.srt` and trigger **Generate Plot** to synthesize a linear narrative plot summary via LLM.
* **Video-Only Ingestion:** Upload a video, run the **Transcription Pipeline** (WhisperX) to generate an `.srt`, then synthesize the `.txt` plot summary.
* **Batch Generation:** Use the **Generate Missing Plots** feature at the Season level to batch-synthesize missing text summaries from existing subtitle tracks.

> [!IMPORTANT]
> **Scholar Review & Correction:** Because LLM-generated plot summaries serve as the foundational source material for the multi-agent narrative analysis, scholars should always review the generated plots from the  and make qualitative corrections directly in the UI before running the analysis engine.

### Step 2: Orchestrate the Analysis
Switch to the **Analysis Engine** panel to run targeted background operations:
* **Narrative Arc Extraction:** Triggers multi-agent workflows over a single episode, season, or entire series to build thematic profiles.
* **Event-Driven Video Analysis:** Processes video/subtitle pairs to slice narrative events into physical clips via FFmpeg and map them to known arcs.

### Step 3: Explore & Visualize Results
Open the **Visualization Dashboard** to interpret the data:
* Use the **Timeline** to study serial pacing and arc distribution.
* Explore the **Vector Store** to identify semantic recurrences across different seasons.
* Stream visual evidence directly via the **Event-Driven Video Player**.

---

## 🧭 UI & Workspace Navigation

The sidebar acts as the primary cockpit for the framework:

### 1. Active Panels
* **Series Manager & File Upload:** The ingestion workspace for library curation and text synthesis.
* **Analysis Engine:** The control center for executing multi-agent background workers.
* **Narrative Arcs Dashboard:** The visualization platform subdivided into *Timeline*, *Vector Store*, and *Characters*.
* **Event Driven Video Analysis:** The interface for inspecting timestamped narrative events and reviewing clipped video clips.
* **Settings:** Live management UI for LLM providers and API keys.

### 2. Global Workspace Controls
* **Add Series Form:** Quickly initialize a new dataset folder structure by specifying a short code and display name.
* **Library Switcher:** Toggle instantly between active series profiles; updating the workspace target dynamically across all views.

---

## ⚙️ Quick Start

The fastest way to launch **ANTS** is by using the unified startup script, which automatically configures both local environment and binaries.

### 1. Prerequisites
* **Python 3.10+**
* **Node.js 18+** *(Required only for initial frontend compilation)*

### 2. Launching the Framework
1. Clone the repository and navigate to the project root folder.
2. Run the automated startup script:
   ```bash
   python run_app.py
   ```

3. The script will dynamically orchestrate the following:
* Build a Python virtual environment (`.venv`) and install dependencies.
* Detect your operating system and place correct local `ffmpeg`/`ffprobe` binaries inside `backend/bin/`.
* Compile and build static production assets for the frontend workspace.
* Spin up the FastAPI server and launch the app in your browser at `http://localhost:8000`.



### 3. Core Configuration

1. Open the **Settings** panel from the sidebar inside the app web UI.
2. Input your preferred LLM provider configurations (OpenAI, Azure, Anthropic, Ollama, etc.) and credentials.
3. Save settings. This automatically creates and updates your secure `backend/.env` file.

---

## 🛠️ Developer Setup & Architecture

For active development or modifying backend and frontend modules independently:

### 📐 Technical Architecture & Stack

* **Backend Framework:** Python 3.10+, FastAPI, SQLModel (SQLite storage layer)
* **Agent Orchestration:** LangGraph (multi-agent workflows), LiteLLM (multi-provider LLM interfacing)
* **ML & Processing Pipeline:** WhisperX (speech-to-text), PyTorch (CUDA-optimized processing), FFmpeg/FFprobe CLI wrappers (video engineering)
* **Vector Vector Store:** ChromaDB (high-dimensional narrative beat embeddings)
* **Frontend Ecosystem:** React 18, TypeScript, Vite, Chakra UI, Plotly.js (3D PCA rendering)

### 1. External Binaries

Ensure `ffmpeg` and `ffprobe` are available on your system `PATH`, or explicitly place compiled binaries in the `backend/bin/` directory so the automation pipelines can locate them.

### 2. Manual Backend Bootstrapping

Activate the isolated virtual environment and initialize the FastAPI development server:

```bash
cd backend
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.api.main:app --reload

```

> *Note: Database models and vector collections will initialize automatically under `backend/narrative_storage/`.*

### 3. Manual Frontend Bootstrapping

Launch the React Vite development server (proxies API requests natively to port `8000`):

```bash
cd frontend
npm install
npm run dev

```

The client dashboard will run on `http://localhost:3000`.

---

## 🔑 Environment Configuration

The framework manages variables dynamically via the **Settings UI** or via direct modification of `backend/.env`.

### Core LLM & Embedding Layer

| Variable | Description |
| --- | --- |
| **LLM_API_KEY** | Authentication key for your chosen language model provider. |
| **LLM_API_BASE** | Target endpoint URL for the API provider. |
| **LLM_MODEL** | Identification string for the model (e.g., `gpt-4o`, `claude-3-5-sonnet`). |
| **EMBED_API_KEY** | Authentication key for the vector embedding provider. |
| **EMBED_API_BASE** | Target endpoint URL for the embedding provider. |

### Advanced Engine Parameters

| Variable | Default Value | Description |
| --- | --- | --- |
| **LLM_PROVIDER** | `""` (derived) | Provider engine string (`openai`, `azure`, `anthropic`, `ollama`). |
| **EMBED_PROVIDER** | `""` (derived) | Embedding engine string (`openai`, `azure`, `cohere`). |
| **EMBED_MODEL** | `embed-v-4-0` | Model configuration string for text vectorization. |

---

*Created by media scholars, for media scholars.*