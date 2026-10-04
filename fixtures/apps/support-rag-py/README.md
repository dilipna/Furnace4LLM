# Kilnworks Assist

Customer-support chatbot for Kilnworks (a fictional kiln-monitoring service). It answers questions
from the product documentation and hands off to a human through support tickets.

## Architecture

- **FastAPI** backend with a streaming `/chat` endpoint.
- **GPT-4o** generates answers from the retrieved documentation.
- Documentation search over `docs/` with keyword ranking.
- Ticket creation through the helpdesk API, always confirmed by the user first.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```
