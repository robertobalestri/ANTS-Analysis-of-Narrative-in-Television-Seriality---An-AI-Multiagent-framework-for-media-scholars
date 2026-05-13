<p align="center">
  <img src="assets/ants%20logo.png" width="600" alt="ANTS Logo">
</p>

# ANTS: Analysis of Narrative in Television Seriality

**ANTS** is an advanced AI-powered multi-agent framework designed specifically for media scholars and narrative analysts. It provides a comprehensive suite of tools for extracting, analyzing, and visualizing complex narrative structures in long-form television content.

## 🚀 Key Features

### 🏛️ Library & Metadata Management
- **Automated Series Ingestion**: Create series with just a code and name.
- **IMDb Integration**: Automatically retrieves official posters and series metadata from the IMDb API.
- **Hierarchical Management**: Organize your research by Series, Seasons, and Episodes.
- **Intelligent Status Tracking**: Visual indicators for file presence (SRTs, Plots) and analysis readiness.

### 🧠 Multi-Agent Analysis Engine
- **Narrative Arc Extraction**: Identify and track story threads across multiple episodes using multi-agent workflows.
- **Character Profiling**: Automatically extract and stabilize character identities.
- **Semantic Progression**: Map the evolution of narrative arcs using high-dimensional embeddings.
- **Vector Search**: Perform semantic queries across the entire series narrative beats.

### 📊 Visualization Dashboard
- **Interactive Timeline**: Visualize narrative arcs and their presence across episodes in a high-fidelity timeline.
- **Vector Store Explorer**: Discover semantic relationships and clusters between narrative segments.
- **Character Network**: Track character appearances and roles within the series.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLModel (SQLite), LiteLLM (multi-provider support).
- **Frontend**: React, TypeScript, Vite, Chakra UI, Plotly.js.
- **Vector Database**: ChromaDB.

---

## ⚙️ Quick Start

The easiest way to start **ANTS** is by using the unified startup script.

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** (Required only for the first build or development)

### 2. Launching the App
1. Clone the repository and navigate to the root folder.
2. Run the unified startup script:
   ```bash
   python run_app.py
   ```
3. The script will automatically:
   - Create a virtual environment and install Python dependencies.
   - (Optional) Build the frontend if not already present.
   - Start the backend server and open the application in your browser at `http://localhost:8000`.

### 3. Initial Configuration
Once the application is running:
1. Open the **Settings** panel from the sidebar.
2. Enter your LLM provider details (OpenAI, Azure, etc.) and API keys.
3. Save the settings. Your configuration is stored in `backend/.env`.

---

## 🛠️ Manual Setup (Developers)

If you wish to run backend and frontend separately for development:

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.api.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
The dev server will run on `http://localhost:3000` and proxy API calls to the backend.

---

## 🔑 Environment Variables

The system requires the following core variables (managed via **Settings** UI):

| Variable | Description |
| :--- | :--- |
| **LLM_PROVIDER** | e.g., `openai`, `azure`, `anthropic`, `ollama` |
| **LLM_MODEL** | The specific model name (e.g., `gpt-4o`) |
| **LLM_API_KEY** | Your secret API key |
| **EMBED_PROVIDER** | Provider for embeddings (e.g., `openai`, `azure`) |
| **EMBED_MODEL** | Model for vectorization (e.g., `text-embedding-3-small`) |

*Note: Technical settings like database paths and log levels are pre-configured but can be manually edited in `backend/.env` if needed.*

---

## 📖 How to Use

### Step 1: Manage your Library
Go to the **Series Manager** in the sidebar. Create a new series (e.g., code: `B99`, name: `Brooklyn Nine-Nine`). The system will automatically fetch the official poster. Add seasons and episodes, and drag-and-drop your `.txt` plot files or `.srt` subtitle files into the episode details view.

### Step 2: Analyze
Switch to the **Analysis Engine**. Select your series and run the multi-agent analysis for a single episode, an entire season, or the whole series. The system will process the text, extract entities, and identify stable narrative arcs.

### Step 3: Explore
Once analysis is complete, open the **Visualization Dashboard**. 
- Use the **Timeline** to see which arcs appear in which episodes.
- Explore the **Vector Store** to find semantically similar story beats across the series.
- View the **Character** tab to analyze narrative importance and appearances.

---

## 🤝 Contributing
Contributions are welcome! Please ensure you follow the coding standards and submit a pull request for any new features or bug fixes.

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

---
*Created by media scholars, for media scholars.*