from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.chat_service import generate_chat_response

router = APIRouter(prefix="/api/chat", tags=["AI Conversational Assistant"])

@router.post("", response_model=ChatResponse, summary="Send message to AI Engineer Assistant")
async def chat_with_assistant(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Interact with the Gemini-powered or offline rule-based Anaerobic Digestion AI Engineer.
    Incorporates real-time IoT telemetry context for grounded expert advice.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty."
        )
    
    try:
        response = await generate_chat_response(request, db)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat assistant error: {str(e)}"
        )
