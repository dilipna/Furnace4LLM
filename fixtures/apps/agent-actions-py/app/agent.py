import json

from openai import OpenAI

from app.config import LLM_BASE_URL, LLM_MODEL, MAX_TOOL_ROUNDS
from app.prompts import SYSTEM_PROMPT
from app.tools import TOOL_SPECS, issue_refund, search_orders, send_email

client = OpenAI(base_url=LLM_BASE_URL, api_key="local")


def run_agent(message: str, confirm_refund: bool = False) -> str:
    """Tool-calling loop: the model may call tools until it answers."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=TOOL_SPECS,
            temperature=0.2,
            max_tokens=512,
        )
        choice = resp.choices[0].message
        if not choice.tool_calls:
            return choice.content or ""
        messages.append(choice.model_dump(exclude_none=True))
        for call in choice.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            if call.function.name == "search_orders":
                result = search_orders(**args)
            elif call.function.name == "issue_refund":
                result = issue_refund(args["order_id"], args["amount"], approved=confirm_refund)
            elif call.function.name == "send_email":
                result = send_email(**args)
            else:
                result = {"error": f"unknown tool {call.function.name}"}
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
            )
    return "I could not finish that request; please try again."
