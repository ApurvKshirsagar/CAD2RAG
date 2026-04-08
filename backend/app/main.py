from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import upload, query

app = FastAPI(
    title="DXF & PDF Query App",
    description="Upload DXF or PDF files and query them using Gemini AI",
    version="1.0.0"
)

# CORS — allows the frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(query.router, prefix="/api", tags=["Query"])

@app.get("/health")
def health_check():
    return {"status": "ok"}