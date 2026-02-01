"""
Test script for Model Semaphore (Concurrency Control)

What it tests:
    asyncio.Semaphore limits concurrent GPU access (default: 1)
    Qdrant semaphore limits concurrent database queries (default: 3x model concurrency)

Expected behavior:
    With MAX_CONCURRENT_INFERENCES=1: Model queries complete sequentially
    Qdrant queries can have higher concurrency (3x) since they're lighter operations
    Check server logs for "Model semaphore created" and "Qdrant semaphore created"

Usage:
    1. Start the server: make dev
    2. Run this script: python scripts/test_semaphore.py
"""

import asyncio
import time
from uuid import UUID, uuid4

import httpx

BASE_URL = "http://localhost:8000"
# Replace with your actual token or set AUTH_ENABLED=false in .env
# If AUTH_ENABLED=false, you can use an empty headers dict
HEADERS = {}  # Set to {"Authorization": "Bearer YOUR_TOKEN"} if auth is enabled


async def send_query(client: httpx.AsyncClient, query_id: int, session_id: UUID):
    """Send a query and measure timing"""
    start = time.time()
    print(f"[Query {query_id}] Starting...")

    try:
        response = await client.post(
            f"{BASE_URL}/query/",
            params={
                "query": "What is this document about?",
                "session_id": str(session_id),
                "top_k": 3,
            },
            headers=HEADERS,
            timeout=120.0,
        )
        elapsed = time.time() - start
        if response.status_code == 422:
            print(f"[Query {query_id}] Validation Error - Response: {response.text}")
        print(
            f"[Query {query_id}] Completed in {elapsed:.2f}s - Status: {response.status_code}"
        )
        return response.status_code, elapsed
    except httpx.TimeoutException:
        elapsed = time.time() - start
        print(f"[Query {query_id}] Timed out after {elapsed:.2f}s")
        return None, elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"[Query {query_id}] Failed after {elapsed:.2f}s - Error: {e}")
        return None, elapsed


async def main():
    """Send 5 concurrent queries - with semaphore=1, they should serialize"""
    print("=" * 60)
    print("Testing Model Semaphore (Concurrency Control)")
    print("=" * 60)
    print(
        "\nWith MAX_CONCURRENT_INFERENCES=1, queries should execute sequentially."
    )
    print("Check server logs for timing to confirm serialization.\n")

    # IMPORTANT: Replace this with a session_id that has indexed documents
    # You can find available session_ids by checking your Qdrant collection
    # or by ingesting a PDF first
    
    # Use the session_id from your collection logs:
    session_id = UUID("04ab7ffe-1e89-4e2a-a2da-0be16476c8b3")
        
    print(f"Using session_id: {session_id}")
    print("NOTE: Make sure this session_id has indexed documents in your collection\n")

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        tasks = [send_query(client, i, session_id) for i in range(5)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)
    print(f"Total time for 5 concurrent requests: {total_time:.2f}s")

    # Calculate if queries were serialized
    individual_times = [r[1] for r in results if r[1] is not None]
    if individual_times:
        avg_time = sum(individual_times) / len(individual_times)
        print(f"Average individual query time: {avg_time:.2f}s")
        print("\nIf semaphore is working (serial execution):")
        print("  - Total time should be close to sum of individual times")
        print(f"  - Expected: ~{avg_time * 5:.2f}s (5 x {avg_time:.2f}s)")
        print("\nIf queries ran in parallel:")
        print("  - Total time would be close to max individual time")


if __name__ == "__main__":
    asyncio.run(main())
