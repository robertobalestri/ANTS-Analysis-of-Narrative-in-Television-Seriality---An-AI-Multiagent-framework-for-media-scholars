# ANTS: Developer Guide

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

The framework manages variables dynamically via the **Settings UI** or via direct manual modification of `backend/.env`.

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