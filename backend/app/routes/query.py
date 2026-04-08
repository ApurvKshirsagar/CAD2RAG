from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.query_handler import handle_query

router = APIRouter()


class QueryRequest(BaseModel):
    session_id: str
    question: str


@router.post("/query")
async def query_file(request: QueryRequest):
    """
    Takes a session_id and a question.
    Returns Gemini's answer based on the uploaded file's content.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if not request.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id cannot be empty.")

    result = handle_query(request.session_id, request.question)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result