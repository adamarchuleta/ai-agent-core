from __future__ import annotations

import json
import os
from typing import Any, Literal

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field


APP_TITLE = "AI Agent Core"
MEMORY_API_BASE = os.getenv("MEMORY_API_BASE", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "20"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


app = FastAPI(title=APP_TITLE)


class AgentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    topic: str | None = None


class AgentDecision(BaseModel):
    intent: Literal["save_memory", "search_memory", "chat"]
    reason: str
    topic: str


class AgentResponse(BaseModel):
    decision: AgentDecision
    reply: str
    memory_context: str | None = None
    tool_result: dict[str, Any] | None = None


def normalize_topic(value: str | None, fallback_text: str) -> str:
    if value and value.strip():
        return "-".join(value.strip().lower().split())

    lowered = fallback_text.lower()

    topic_keywords = {
        "work": ["meeting", "project", "deadline", "client", "manager", "job"],
        "personal": ["birthday", "family", "friend", "favorite", "love", "home"],
        "health": ["doctor", "medication", "workout", "sleep", "diet"],
        "travel": ["flight", "hotel", "trip", "travel", "airport", "vacation"],
        "preferences": ["prefer", "favorite", "like", "dislike", "usually"],
    }

    for topic, keywords in topic_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            return topic

    return "general"


def classify_intent_fallback(message: str) -> tuple[Literal["save_memory", "search_memory", "chat"], str]:
    lowered = message.lower().strip()

    save_patterns = [
        "remember that",
        "save this",
        "don't forget",
        "for future reference",
        "my favorite",
        "i prefer",
        "i like",
        "i dislike",
    ]
    search_patterns = [
        "what do you remember",
        "do you remember",
        "what's my",
        "what is my",
        "where do i",
        "when is my",
        "who is my",
        "recall",
        "search memory",
    ]

    if any(pattern in lowered for pattern in save_patterns):
        return "save_memory", "Fallback classifier: the message looks like a durable fact or preference worth storing."

    if any(pattern in lowered for pattern in search_patterns):
        return "search_memory", "Fallback classifier: the message appears to be asking for previously stored information."

    if lowered.endswith("?"):
        return "search_memory", "Fallback classifier: the message is phrased as a question, so memory lookup is worth trying first."

    return "chat", "Fallback classifier: no explicit save or search signal was detected."


async def classify_intent_with_llm(
    message: str,
    topic: str,
) -> tuple[Literal["save_memory", "search_memory", "chat"], str, str]:
    if not OPENAI_API_KEY:
        intent, reason = classify_intent_fallback(message)
        return intent, reason, topic

    system_prompt = (
        "You are an intent router for an AI agent. "
        "Classify the user's message into exactly one of these intents: "
        "save_memory, search_memory, or chat. "
        "Return strict JSON only with keys: intent, reason, topic. "
        "The topic should be short, lowercase, and hyphenated when needed. "
        "Choose save_memory when the user states a durable preference, fact, or detail worth remembering. "
        "Choose search_memory when the user asks for previously stored information or personal context. "
        "Choose chat for everything else."
    )

    user_prompt = (
        f"Message: {message}\n"
        f"Current topic guess: {topic}\n\n"
        "Return JSON like: "
        '{"intent":"save_memory","reason":"...","topic":"preferences"}'
    )

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
            },
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(content)
        intent = parsed.get("intent", "chat")
        reason = parsed.get("reason", "The model returned a routing decision.")
        parsed_topic = normalize_topic(parsed.get("topic"), fallback_text=message)

        if intent not in {"save_memory", "search_memory", "chat"}:
            raise ValueError("Invalid intent returned by model")

        return intent, reason, parsed_topic
    except Exception:
        fallback_intent, fallback_reason = classify_intent_fallback(message)
        return fallback_intent, fallback_reason, topic


async def save_memory(user_id: str, message: str, topic: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            f"{MEMORY_API_BASE}/memory/save",
            json={
                "user_id": user_id,
                "content": message,
                "topic": topic,
                "importance": 4,
                "metadata": {
                    "source": "ai-agent-core",
                    "tags": ["agent"],
                    "extra": {}
                }
            },
        )
        response.raise_for_status()
        return response.json()


async def search_memory(user_id: str, message: str, topic: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            f"{MEMORY_API_BASE}/chat/context",
            json={
                "user_id": user_id,
                "message": message,
                "topic": topic,
                "limit": 5,
            },
        )
        response.raise_for_status()
        return response.json()


def build_chat_reply(message: str, topic: str) -> str:
    return (
        f"You said: '{message}'. "
        f"I treated this as a normal chat turn under the '{topic}' topic. "
        "No tool call was needed."
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": APP_TITLE}


@app.post("/agent/respond", response_model=AgentResponse)
async def agent_respond(payload: AgentRequest) -> AgentResponse:
    initial_topic = normalize_topic(payload.topic, payload.message)
    intent, reason, topic = await classify_intent_with_llm(payload.message, initial_topic)
    decision = AgentDecision(intent=intent, reason=reason, topic=topic)

    if intent == "save_memory":
        result = await save_memory(payload.user_id, payload.message, topic)
        return AgentResponse(
            decision=decision,
            reply="Got it — I saved that to memory.",
            tool_result=result,
        )

    if intent == "search_memory":
        result = await search_memory(payload.user_id, payload.message, topic)
        context_block = result.get("context_block") or "No relevant memories found."
        memories = result.get("memories") or []

        if memories:
            top_memory = memories[0].get("content", "I found something relevant in memory.")
            reply = f"Here’s what I found in memory: {top_memory}"
        else:
            reply = "I checked memory, but I did not find anything relevant yet."

        return AgentResponse(
            decision=decision,
            reply=reply,
            memory_context=context_block,
            tool_result=result,
        )

    return AgentResponse(
        decision=decision,
        reply=build_chat_reply(payload.message, topic),
        memory_context=None,
        tool_result=None,
    )
