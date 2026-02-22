# Models Module

The models module previously contained Pydantic data models for structured API responses (e.g., `Reference`, `FinalResponse`). These models have been removed as the query endpoint now streams plain text responses via the multimodal LM service instead of structured JSON output.

**Status:** `document-api/src/doc_api/models/query_response.py` has been removed.

## Current Response Format

The query endpoint now returns Server-Sent Events (SSE) with plain text chunks:

```
data: Based on the documents
data: , the key findings include
data: ...
data: [DONE]
```

Response generation is handled by the multimodal LM service (Qwen3-VL-32B-Instruct via vLLM) using the OpenAI-compatible streaming API.
