from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import rag_config
from app.llm import stream_answer
from app.prompts import build_messages
from app.retriever import retrieve
from app.tickets import ApprovalRequired, create_ticket

app = FastAPI(title="Kilnworks Assist")


class ChatRequest(BaseModel):
    question: str


class TicketRequest(BaseModel):
    summary: str
    email: str
    approved: bool = False


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    cfg = rag_config()
    chunks = retrieve(req.question, top_k=cfg["retrieval"]["top_k"])
    messages = build_messages(req.question, chunks, cfg["retrieval"]["max_context_chars"])
    gen = cfg["generation"]
    return StreamingResponse(
        stream_answer(
            messages,
            max_tokens=gen["max_tokens"],
            temperature=gen["temperature"],
            route="/chat",
        ),
        media_type="text/plain",
    )


@app.post("/tickets")
def tickets(req: TicketRequest) -> dict:
    try:
        return create_ticket(req.summary, req.email, approved=req.approved)
    except ApprovalRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
