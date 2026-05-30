from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from ai.copilot import CoPilotAgent

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str
    context: str = ""

@router.post("/chat")
async def ai_chat(req: ChatRequest, request: Request):
    bus = request.app.state.bus
    
    # Initialize the agent (in production, this might be stateful/singleton)
    agent = CoPilotAgent(bus)
    
    reply = await agent.process_message(req.prompt, req.context)
    
    return {"reply": reply}
