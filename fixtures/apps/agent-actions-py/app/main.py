from fastapi import FastAPI
from pydantic import BaseModel

from app.agent import run_agent

app = FastAPI(title="Kilnworks order agent")


class ChatIn(BaseModel):
    message: str
    confirm_refund: bool = False


@app.post("/agent/chat")
def chat(body: ChatIn) -> dict:
    return {"answer": run_agent(body.message, confirm_refund=body.confirm_refund)}


@app.get("/health")
def health() -> dict:
    return {"ok": True}
