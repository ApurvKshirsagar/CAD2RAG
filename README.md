# CAD2RAG

By: Apurv Ravindra Kshirsagar

Query your CAD drawings and PDF documents using natural language, powered by Gemini AI.

Upload one or more DXF or PDF files (up to 5 per session), then ask questions across all of them in plain English. DXF files are parsed into a Neo4j graph database for structured querying. PDFs are extracted with PyMuPDF — every page is always rasterised to a high-resolution image (300 DPI); if the PDF also contains extractable text it is chunked and sent as text context, otherwise the page images are sent directly to Gemini Vision.

---

## Architecture

```
Upload (DXF or PDF — up to 5 files per session)
        │
        ▼
   File Router
   ┌─────┴──────┐
  DXF          PDF
   │             │
ezdxf        PyMuPDF
   │          ┌──┴──────────────────────────┐
Neo4j         │  Always: render every page   │
(graph DB)    │  to 300 DPI PNG → base64     │
   │          │                              │
   │          ├─ Text extractable?           │
   │          │   YES → chunk text (2000c)   │
   │          │   NO  → image-only mode      │
   │          └──────────────────────────────┘
   │                        │
   └──────────┬─────────────┘
              ▼
       Session Store
    (in-memory, multi-file)
              │
              ▼
       Query Handler
    ┌──────────┴──────────────────────┐
    │ Single file      Multiple files │
    │                                 │
    │ DXF → Cypher    Merge all       │
    │ → text context  contexts into   │
    │                 one Gemini call │
    │ PDF text →      (labelled by    │
    │ text context    filename)        │
    │                                 │
    │ PDF image →     Image PDFs cap  │
    │ vision call     at 3 pages/file │
    └──────────┬──────────────────────┘
               ▼
           Gemini API
      (gemini-2.5-pro)
               │
               ▼
       Response → Frontend
```

### DXF Pipeline

1. File uploaded → saved to `backend/uploads/`
2. Pre-processed to fix malformed scientific notation
3. Parsed with `ezdxf` → entities, layers, metadata extracted
4. Written to Neo4j as a labelled graph (`DXFMetadata`, `Layer`, `Entity` nodes)
5. On query → relevant nodes fetched via Cypher → sent to Gemini as text context

### PDF Pipeline

1. File uploaded → saved to `backend/uploads/`
2. **Every page is always rendered** to a 300 DPI PNG and base64-encoded
3. Text is extracted page-by-page; if found, chunked into ~2000-char pieces with 200-char overlap
4. `is_image_based` flag set — `True` when zero text pages were found
5. All data stored in-memory under the session
6. On query:
   - **Text-extractable PDF** → text chunks sent to Gemini as context
   - **Image-based PDF** (scans, drawings) → base64 page images sent to Gemini Vision (capped at 10 pages across all files in a multi-file session, or 5 for a single file)

### Multi-file Session Flow

1. `POST /api/session` → creates an empty session, returns `session_id`
2. `POST /api/upload?session_id=…` → process and attach each file (up to 5)
3. `POST /api/query` → query handler merges context from all files in one Gemini call; answers reference filenames where relevant

---

## Tech Stack

| Layer          | Technology                         |
| -------------- | ---------------------------------- |
| Backend        | FastAPI + Uvicorn                  |
| DXF Parsing    | ezdxf                              |
| PDF Parsing    | PyMuPDF (fitz) — text + vision     |
| Graph Database | Neo4j 5.19 (Docker)                |
| AI             | Google Gemini API (gemini-2.5-pro) |
| Frontend       | Vanilla HTML / CSS / JS            |
| Session Store  | In-memory (Python dict with TTL)   |

---

## Project Structure

```
CAD2RAG/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Env vars & settings
│   │   ├── routes/
│   │   │   ├── upload.py           # POST /api/session, POST /api/upload
│   │   │   └── query.py            # POST /api/query
│   │   ├── services/
│   │   │   ├── file_router.py      # DXF vs PDF detection
│   │   │   ├── dxf_parser.py       # ezdxf extraction
│   │   │   ├── graph_builder.py    # Neo4j writer + Cypher query
│   │   │   ├── pdf_parser.py       # PyMuPDF text + image extraction
│   │   │   ├── query_handler.py    # Single & multi-file query routing
│   │   │   └── gemini_client.py    # Gemini text, vision & multi-context
│   │   ├── db/
│   │   │   ├── neo4j_client.py     # Neo4j driver singleton
│   │   │   └── session_store.py    # Multi-file session manager (TTL)
│   │   └── utils/
│   │       └── helpers.py
│   ├── uploads/                    # Temp file storage (gitignored)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── docker-compose.yml              # Neo4j only
└── README.md
```

---

## Prerequisites

- Python 3.12+
- Docker Desktop (for Neo4j only)
- A Google Gemini API key → [aistudio.google.com](https://aistudio.google.com)

---

## Setup & Running

### 1. Clone the repo

```bash
git clone https://github.com/your-username/CAD2RAG.git
cd CAD2RAG
```

### 2. Start Neo4j via Docker

```bash
docker-compose up -d
```

Neo4j browser will be available at `http://localhost:7474`
Default credentials: `neo4j / your_neo4j_password_here`

### 3. Set up Python environment

```bash
cd backend
pip install -r requirements.txt
```

> If using conda/miniforge and PyMuPDF fails to install:
>
> ```bash
> conda install -c conda-forge pymupdf -y
> ```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=50
SESSION_TTL_SECONDS=3600
```

### 5. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API will be live at `http://127.0.0.1:8000`
Swagger docs at `http://127.0.0.1:8000/docs`

### 6. Open the frontend

```bash
cd frontend
python -m http.server 3000
```

or just open `frontend/index.html` directly in your browser — no build step needed.

---

## API Endpoints

### `POST /api/session`

Create a new empty session before uploading files.

**Response:**

```json
{
  "session_id": "uuid",
  "max_files": 5
}
```

### `POST /api/upload?session_id={uuid}`

Upload a `.dxf` or `.pdf` file and attach it to the session.

**Request:** `multipart/form-data` with `file` field + `session_id` query param

**Response:**

```json
{
  "session_id": "uuid",
  "file_type": "dxf",
  "filename": "drawing.dxf",
  "file_id": "uuid",
  "status": "ready",
  "summary": { "layers": 3, "entities": 504, "metadata": {} },
  "files_in_session": 1,
  "max_files": 5,
  "slots_remaining": 4
}
```

### `POST /api/query`

Ask a question across all files in the session.

**Request:**

```json
{
  "session_id": "uuid",
  "question": "Which room is beside the operation room?"
}
```

**Response:**

```json
{
  "session_id": "uuid",
  "question": "Which room is beside the operation room?",
  "answer": "Based on the floor plan drawing...",
  "files_queried": ["hospital_floor1.pdf", "hospital_floor2.dxf"],
  "context_used": "..."
}
```

### `GET /health`

Returns `{ "status": "ok" }`

---

## Example Queries

**For DXF files:**

- "How many layers are in this drawing?"
- "What entity types exist and how many of each?"
- "Describe the geometry in layer 0"
- "How many lines are there?"

**For PDF floor plans / drawings (image-based):**

- "Which room is beside the operation room?"
- "Where is the emergency exit on this floor?"
- "List all the rooms visible on this floor plan"

**For text PDFs:**

- "Summarize this document"
- "What are the key points on page 2?"
- "Find any mentions of deadlines or dates"

**Multi-file queries:**

- "Compare the layouts of both drawings"
- "Does floor 1 and floor 2 have the same number of rooms?"
- "What changed between version 1 and version 2 of this document?"

---

## Known Limitations

- Sessions are stored in-memory — they reset when the backend restarts
- Maximum 5 files per session (Gemini API context window constraint)
- Image-based PDFs cap at 3 pages per file (10 total) in multi-file sessions to stay within Gemini's token limits
- DXF files with severely malformed encoding may still fail to parse
- Free tier Gemini API has rate limits — add billing at [aistudio.google.com](https://aistudio.google.com) for heavy usage

---

## Notes

- The `docker-compose.yml` runs Neo4j only — the backend runs directly with uvicorn, not in Docker
- Uploaded files are saved to `backend/uploads/` and are gitignored
- Fixed DXF files (scientific notation patch) are saved as `*_fixed.dxf` alongside the original
- Multi-file sessions are created first via `POST /api/session`, then files are attached one by one via `POST /api/upload?session_id=…`

---

## Built With

- [FastAPI](https://fastapi.tiangolo.com)
- [ezdxf](https://ezdxf.readthedocs.io)
- [PyMuPDF](https://pymupdf.readthedocs.io)
- [Neo4j](https://neo4j.com)
- [Google Gemini](https://ai.google.dev)
