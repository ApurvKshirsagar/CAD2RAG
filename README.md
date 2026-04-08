# CAD2RAG

Query your CAD drawings and PDF documents using natural language, powered by Gemini AI.

Upload a DXF or PDF file, and ask questions about it in plain English. DXF files are parsed into a Neo4j graph database for structured querying. PDFs are extracted and sent directly as context to Gemini.

---

## Architecture

```
Upload (DXF or PDF)
        │
        ▼
   File Router
   ┌─────┴──────┐
  DXF          PDF
   │             │
ezdxf        PyMuPDF
   │             │
Neo4j        Text chunks
(graph DB)   (in-memory)
   │             │
   └─────┬───────┘
         ▼
    Query Handler
         │
         ▼
      Gemini API
         │
         ▼
   Response → Frontend
```

### DXF Pipeline

1. File uploaded → saved to `backend/uploads/`
2. Pre-processed to fix malformed scientific notation
3. Parsed with `ezdxf` → entities, layers, metadata extracted
4. Written to Neo4j as a labeled graph (nodes: `DXFMetadata`, `Layer`, `Entity`)
5. On query → relevant nodes fetched via Cypher → sent to Gemini as context

### PDF Pipeline

1. File uploaded → saved to `backend/uploads/`
2. Text extracted page-by-page with PyMuPDF
3. Chunked into ~2000 char pieces with overlap
4. Stored in-memory under a session ID
5. On query → chunks sent to Gemini as context

---

## Tech Stack

| Layer          | Technology                       |
| -------------- | -------------------------------- |
| Backend        | FastAPI + Uvicorn                |
| DXF Parsing    | ezdxf                            |
| PDF Parsing    | PyMuPDF (fitz)                   |
| Graph Database | Neo4j 5.19 (Docker)              |
| AI             | Google Gemini API                |
| Frontend       | Vanilla HTML / CSS / JS          |
| Session Store  | In-memory (Python dict with TTL) |

---

## Project Structure

```
CAD2RAG/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Env vars & settings
│   │   ├── routes/
│   │   │   ├── upload.py           # POST /api/upload
│   │   │   └── query.py            # POST /api/query
│   │   ├── services/
│   │   │   ├── file_router.py      # DXF vs PDF detection
│   │   │   ├── dxf_parser.py       # ezdxf extraction
│   │   │   ├── graph_builder.py    # Neo4j writer + query
│   │   │   ├── pdf_parser.py       # PyMuPDF extraction
│   │   │   ├── query_handler.py    # Routes query to right source
│   │   │   └── gemini_client.py    # Gemini API wrapper
│   │   ├── db/
│   │   │   ├── neo4j_client.py     # Neo4j driver singleton
│   │   │   └── session_store.py    # In-memory session manager
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
open frontend/index.html
```

Or just drag `frontend/index.html` into your browser. No build step needed.

---

## API Endpoints

### `POST /api/upload`

Upload a `.dxf` or `.pdf` file.

**Request:** `multipart/form-data` with `file` field

**Response:**

```json
{
  "session_id": "uuid",
  "file_type": "dxf",
  "filename": "drawing.dxf",
  "status": "ready",
  "summary": {
    "layers": 3,
    "entities": 504,
    "metadata": { ... }
  }
}
```

### `POST /api/query`

Ask a question about an uploaded file.

**Request:**

```json
{
  "session_id": "uuid",
  "question": "How many layers are in this drawing?"
}
```

**Response:**

```json
{
  "session_id": "uuid",
  "file_type": "dxf",
  "question": "How many layers are in this drawing?",
  "answer": "This drawing contains 3 layers...",
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
- "How many lines are in this drawing?"
- "Are there any text annotations?"

**For PDF files:**

- "Summarize this document"
- "What are the key points on page 2?"
- "Find any mentions of deadlines or dates"

---

## Known Limitations

- Sessions are stored in-memory — they reset when the backend restarts
- DXF files with severely malformed encoding may still fail to parse
- Free tier Gemini API has rate limits — add billing at [aistudio.google.com](https://aistudio.google.com) for heavy usage
- Large PDFs (500+ pages) may exceed Gemini's context window; only the first 5 chunks are sent

---

## Notes

- The `docker-compose.yml` runs Neo4j only — the backend runs directly with uvicorn, not in Docker
- Uploaded files are saved to `backend/uploads/` and are gitignored
- Fixed DXF files (scientific notation patch) are saved as `*_fixed.dxf` alongside the original

---

## Built With

- [FastAPI](https://fastapi.tiangolo.com)
- [ezdxf](https://ezdxf.readthedocs.io)
- [PyMuPDF](https://pymupdf.readthedocs.io)
- [Neo4j](https://neo4j.com)
- [Google Gemini](https://ai.google.dev)
