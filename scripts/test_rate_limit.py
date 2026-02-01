"""
Test script for Rate Limiting

What it tests:
    slowapi rate limiter limits requests per minute
    - /query/: 30 requests/minute (configurable via QUERY_RATE_LIMIT)
    - /ingest-pdfs/: 10 requests/minute (configurable via INGEST_RATE_LIMIT)

Expected behavior:
    - First N requests: 200 or 400 (depending on request validity)
    - Request N+1: 429 Too Many Requests

Usage:
    1. Start the server: make dev
    2. Optionally set stricter limits for testing:
       INGEST_RATE_LIMIT=3/minute in .env
    3. Run this script: python scripts/test_rate_limit.py
"""

import asyncio
from uuid import UUID

import httpx

BASE_URL = "http://localhost:8000"
# Replace with your actual token or set AUTH_ENABLED=false in .env
HEADERS = {"Authorization": "Bearer YOUR_TOKEN"}


async def test_ingest_rate_limit():
    """Send rapid ingest requests to trigger rate limit (default limit: 10/minute)"""
    print("=" * 60)
    print("Testing Rate Limiting on /ingest-pdfs/")
    print("=" * 60)
    print("\nDefault limit: 10 requests/minute")
    print("Sending 12 rapid requests to trigger rate limit...\n")

    # IMPORTANT: Replace this with a session_id that has indexed documents
    # You can find available session_ids by checking your Qdrant collection
    # or by ingesting a PDF first
    
    # Use the session_id from your collection logs:
    session_id = UUID("04ab7ffe-1e89-4e2a-a2da-0be16476c8b3")
    
    print(f"Using session_id: {session_id}\n")

    async with httpx.AsyncClient() as client:
        for i in range(12):
            try:
                # Create a minimal PDF-like content
                pdf_content = (
                    b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
                )

                response = await client.post(
                    f"{BASE_URL}/ingest-pdfs/",
                    files=[
                        ("files", ("test.pdf", pdf_content, "application/pdf"))
                    ],
                    params={"session_id": str(session_id)},
                    headers=HEADERS,
                    timeout=10.0,
                )
                print(
                    f"Request {i + 1:2d}: Status {response.status_code}", end=""
                )

                if response.status_code == 429:
                    print(" <- RATE LIMITED!")
                    try:
                        detail = response.json().get("detail", response.text)
                        print(f"           Response: {detail}")
                    except Exception:
                        print(f"           Response: {response.text}")
                    break
                else:
                    print()

            except Exception as e:
                print(f"Request {i + 1:2d}: Error - {e}")


async def test_query_rate_limit():
    """Send rapid query requests to trigger rate limit (default limit: 30/minute)"""
    print("\n" + "=" * 60)
    print("Testing Rate Limiting on /query/")
    print("=" * 60)
    print("\nDefault limit: 30 requests/minute")
    print("Sending 35 rapid requests to trigger rate limit...\n")

    # IMPORTANT: Replace this with a session_id that has indexed documents
    # You can find available session_ids by checking your Qdrant collection
    # or by ingesting a PDF first
    
    # Use the session_id from your collection logs:
    session_id = UUID("04ab7ffe-1e89-4e2a-a2da-0be16476c8b3")
    
    print(f"Using session_id: {session_id}\n")

    async with httpx.AsyncClient() as client:
        for i in range(35):
            try:
                response = await client.post(
                    f"{BASE_URL}/query/",
                    params={
                        "query": "test query",
                        "session_id": str(session_id),
                        "top_k": 1,
                    },
                    headers=HEADERS,
                    timeout=10.0,
                )
                print(
                    f"Request {i + 1:2d}: Status {response.status_code}", end=""
                )

                if response.status_code == 429:
                    print(" <- RATE LIMITED!")
                    try:
                        detail = response.json().get("detail", response.text)
                        print(f"           Response: {detail}")
                    except Exception:
                        print(f"           Response: {response.text}")
                    break
                else:
                    print()

            except Exception as e:
                print(f"Request {i + 1:2d}: Error - {e}")


async def main():
    print("\n" + "=" * 60)
    print("RATE LIMIT TEST SUITE")
    print("=" * 60)
    print("\nTip: For faster testing, set stricter limits in .env:")
    print("  INGEST_RATE_LIMIT=3/minute")
    print("  QUERY_RATE_LIMIT=5/minute")
    print()

    await test_ingest_rate_limit()
    await test_query_rate_limit()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
