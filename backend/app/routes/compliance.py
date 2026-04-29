from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.compliance_checker import run_compliance_check

router = APIRouter()


class ComplianceRequest(BaseModel):
    session_id: str
    rules: list[str]


@router.post("/compliance")
async def compliance_check(request: ComplianceRequest):
    if not request.rules:
        raise HTTPException(status_code=400, detail="No rules provided.")
    if len(request.rules) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 rules per check.")
    if not request.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id cannot be empty.")

    result = await run_compliance_check(request.session_id, request.rules)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result