


# AI Agent Core

A minimal, production-style agent layer for AI systems.

This service acts as the decision-making brain between user input and backend tools like memory, APIs, or external services.

---

## What It Does

The agent:

- Understands user intent
- Decides what action to take
- Calls the appropriate tool (memory, etc.)
- Returns a structured response

---

## Architecture

```
User Input
   ↓
AI Agent Core (decision layer)
   ↓
Memory Backend / Tools
   ↓
Response
```

---

## Features

- Intent classification (save, search, chat)
- Memory tool integration
- Topic normalization
- Structured agent responses
- FastAPI-based API

---

## API

### POST `/agent/respond`

Send a message and let the agent decide what to do.

#### Request

```json
{
  "user_id": "user_123",
  "message": "My favorite food is sushi"
}
```

#### Response

```json
{
  "decision": {
    "intent": "save_memory",
    "reason": "The message looks like a durable fact or preference worth storing.",
    "topic": "preferences"
  },
  "reply": "Got it — I saved that to memory."
}
```

---

## Quick Start

```bash
git clone <your-repo>
cd ai-agent-core

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python -m uvicorn agent:app --reload --port 8001
```

Open:
http://127.0.0.1:8001/docs

---

## Requirements

This agent is designed to work with a memory backend.

By default, it connects to:

```
http://127.0.0.1:8000
```

You can change this using an environment variable:

```env
MEMORY_API_BASE=http://your-backend-url
```

---

## Example Flows

### Save Memory

Input:
> "My favorite gym is Lifetime Fitness"

Agent:
- Detects memory intent
- Calls memory API
- Confirms save

---

### Search Memory

Input:
> "Where do I work out?"

Agent:
- Searches memory
- Returns relevant result

---

## Use Cases

- AI assistants with tool use
- Memory-aware chat systems
- Agent-based AI architectures
- Rapid prototyping of AI workflows

---

## Notes

- Rule-based intent detection (can upgrade to LLM)
- Designed to be simple and extensible
- Plug into voice, chat, or mobile apps

---
## Support

If this project was useful, consider starring the repository.