# Utils Module

The utils module contains utility functions for prompts and Qdrant operations.

## Module Structure

```
src/app/utils/
├── __init__.py
├── prompt_utils.py    # Prompt file reading
└── qdrant_utils.py    # Qdrant operations with retry
```

## Overview

```mermaid
graph TD
    subgraph Utils["Utils Module"]
        Prompt["prompt_utils.py"]
        Qdrant["qdrant_utils.py"]
    end

    subgraph Usage["Usage"]
        Deps["dependencies.py"]
        Ingest["pdf_ingest.py"]
    end

    Deps --> Prompt
    Ingest --> Qdrant
```

---

## prompt_utils.py

Utility functions for reading prompt files.

### read_prompt_from_plain_file

Reads prompt content from a plain text file.

```python
def read_prompt_from_plain_file(file_path: Path) -> str:
    """
    Read prompt content from a plain text file.

    Args:
        file_path: Path to the prompt file

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        logger.error(f"Prompt file not found: {file_path}")
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    logger.info(f"Loaded prompt from {file_path} ({len(content)} chars)")

    return content
```

### Usage Flow

```mermaid
sequenceDiagram
    participant Deps as dependencies.py
    participant Utils as prompt_utils.py
    participant FS as File System
    participant Logger as Loguru

    Note over Deps: Called once (cached)
    Deps->>Utils: read_prompt_from_plain_file(path)

    Utils->>FS: file_path.exists()
    alt File exists
        FS-->>Utils: True
        Utils->>FS: file_path.read_text()
        FS-->>Utils: content
        Utils->>Logger: info("Loaded prompt...")
        Utils-->>Deps: content
    else File not found
        FS-->>Utils: False
        Utils->>Logger: error("Prompt file not found...")
        Utils-->>Deps: raise FileNotFoundError
    end
```

### Prompt Files

| File | Purpose |
|------|---------|
| `prompts/response_1` | System instructions for document analysis |
| `prompts/response_2` | Output format and citation instructions |

### Example

```python
from pathlib import Path
from src.app.utils.prompt_utils import read_prompt_from_plain_file

# Load a prompt
prompt_path = Path("prompts/response_1")
system_prompt = read_prompt_from_plain_file(prompt_path)
```

---

## qdrant_utils.py

Utility functions for Qdrant operations with retry logic.

### upsert_with_retry

Upserts points to Qdrant with automatic retry on failure.

```mermaid
graph TD
    Start["upsert_with_retry()"]

    Attempt1["Attempt 1"]
    Attempt2["Attempt 2\n(1s backoff)"]
    Attempt3["Attempt 3\n(2s backoff)"]

    Success["Return None"]
    Failure["Raise Exception"]

    Start --> Attempt1
    Attempt1 -->|Success| Success
    Attempt1 -->|Exception| Attempt2
    Attempt2 -->|Success| Success
    Attempt2 -->|Exception| Attempt3
    Attempt3 -->|Success| Success
    Attempt3 -->|Exception| Failure
```

### Implementation

```python
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def upsert_with_retry(
    client: AsyncQdrantClient,
    collection_name: str,
    points: list[PointStruct],
) -> None:
    """
    Upsert points to Qdrant with retry logic.

    Args:
        client: Async Qdrant client
        collection_name: Name of the collection
        points: List of points to upsert

    Raises:
        Exception: After 3 failed attempts
    """
    await client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )
```

### Retry Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `stop_after_attempt` | 3 | Maximum retry attempts |
| `wait_exponential.multiplier` | 1 | Base multiplier |
| `wait_exponential.min` | 1 second | Minimum wait time |
| `wait_exponential.max` | 10 seconds | Maximum wait time |
| `before_sleep` | Log warning | Log before each retry |

### Retry Timing

| Attempt | Wait Before |
|---------|-------------|
| 1 | 0s (immediate) |
| 2 | ~1s |
| 3 | ~2s |
| Fail | - |

### Example

```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from src.app.utils.qdrant_utils import upsert_with_retry

# Create points
points = [
    PointStruct(
        id="point-1",
        vector={"default": [0.1, 0.2, ...]},
        payload={"session_id": "123", "document": "doc.pdf", "page": 1}
    )
]

# Upsert with automatic retry
await upsert_with_retry(
    client=qdrant_client,
    collection_name="my_collection",
    points=points,
)
```

---

## Error Handling

### prompt_utils.py

```python
try:
    prompt = read_prompt_from_plain_file(Path("prompts/missing"))
except FileNotFoundError as e:
    print(f"Error: {e}")
```

### qdrant_utils.py

```python
from tenacity import RetryError

try:
    await upsert_with_retry(client, collection, points)
except RetryError as e:
    # All 3 attempts failed
    print(f"Failed after 3 attempts: {e.last_attempt.exception()}")
```

---

## Logging

Both utilities use Loguru for logging:

### prompt_utils.py Logs

```
2024-01-15 10:30:45 | INFO | prompt_utils:read_prompt_from_plain_file:15 | Loaded prompt from prompts/response_1 (1234 chars)
```

```
2024-01-15 10:30:45 | ERROR | prompt_utils:read_prompt_from_plain_file:12 | Prompt file not found: prompts/missing
```

### qdrant_utils.py Logs

```
2024-01-15 10:30:45 | WARNING | retry:before_sleep:85 | Retrying upsert_with_retry in 1.0 seconds as it raised ConnectionError: Connection refused
```

---

## Integration

### In dependencies.py

```python
from functools import lru_cache
from pathlib import Path
from src.app.utils.prompt_utils import read_prompt_from_plain_file

@lru_cache
def get_prompts() -> dict[str, str]:
    prompts_path = Path("prompts")
    return {
        "prompt_1": read_prompt_from_plain_file(prompts_path / "response_1"),
        "prompt_2": read_prompt_from_plain_file(prompts_path / "response_2"),
    }
```

### In pdf_ingest.py

```python
from src.app.utils.qdrant_utils import upsert_with_retry

async def _process_batch(self, ...):
    points = [...]
    await upsert_with_retry(
        self.qdrant_client,
        self.collection_name,
        points,
    )
```
