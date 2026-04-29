from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import upload, query, compliance

app = FastAPI(
    title="CAD2RAG",
    description="Upload DXF or PDF files and query them using Gemini AI",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(query.router, prefix="/api", tags=["Query"])
app.include_router(compliance.router, prefix="/api", tags=["Compliance"])

@app.get("/health")
def health_check():
    return {"status": "ok"}