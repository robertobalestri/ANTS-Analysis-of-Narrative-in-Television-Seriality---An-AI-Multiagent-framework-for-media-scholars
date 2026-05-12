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

## ⚙️ Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher
- An API Key from an LLM provider (OpenAI, Azure, Anthropic, etc. - managed via LiteLLM) for both LLM and embedding models.

### 2. Backend Setup
1. Navigate to the `backend` directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your environment:
   Copy `.env.example` to `.env` and fill in your details:
   ```env
   LLM_API_KEY=your_api_key
   LLM_API_BASE=your_base_url
   LLM_MODEL=gpt-4-turbo-preview
   EMBED_API_KEY=your_embed_api_key
   EMBED_API_BASE=your_embed_base_url
   ```

### 3. Frontend Setup
1. Navigate to the `frontend` directory.
2. Install node modules:
   ```bash
   npm install
   ```

---

## 🏃 How to Run

### Start the Backend
From the `backend` directory:
```bash
uvicorn app.api.main:app --reload
```
The API will be available at `http://localhost:8000`.

### Start the Frontend
From the `frontend` directory:
```bash
npm run dev
```
Access the application at `http://localhost:3000`.

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