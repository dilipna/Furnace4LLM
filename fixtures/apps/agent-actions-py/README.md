# Kilnworks order agent

A tool-calling assistant for Kilnworks customer orders. It looks up orders, issues refunds
(after the customer confirms) and sends follow-up emails. FastAPI service; the model is
served by vLLM through its OpenAI-compatible API.

See `docs/architecture.md` for how a request flows through the service.

## Run

    pip install -r requirements.txt
    docker compose up -d vllm
    uvicorn app.main:app --port 8200

`POST /agent/chat` with `{"message": "...", "confirm_refund": false}`.
