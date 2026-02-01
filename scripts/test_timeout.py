"""
Test script for Request Timeouts

What it tests:
    TimeoutMiddleware returns 504 Gateway Timeout after INGEST_ENDPOINT_TIMEOUT_SECONDS and QUERY_ENDPOINT_TIMEOUT_SECONDS
    (default: 300 seconds)

Expected behavior:
    - Status: 504 Gateway Timeout
    - Response: {"detail": "Request timed out after X seconds"}

Usage:
    1. Set a short timeout for testing: INGEST_ENDPOINT_TIMEOUT_SECONDS=5 and QUERY_ENDPOINT_TIMEOUT_SECONDS=5 in .env
    2. Restart the server: make dev
    3. Run this script: python scripts/test_timeout.py

Note:
    With the default 300 second timeout, this test would take 5 minutes.
    Set INGEST_ENDPOINT_TIMEOUT_SECONDS=5 and QUERY_ENDPOINT_TIMEOUT_SECONDS=5 for quick testing.
"""

import time

import httpx
from uuid import UUID

BASE_URL = "http://localhost:8000"
# Replace with your actual token or set AUTH_ENABLED=false in .env
HEADERS = {"Authorization": "Bearer YOUR_TOKEN"}


def test_timeout():
    """Test request timeout - requires INGEST_ENDPOINT_TIMEOUT_SECONDS and QUERY_ENDPOINT_TIMEOUT_SECONDS to be set low"""
    print("=" * 60)
    print("Testing Request Timeout")
    print("=" * 60)
    print(
        "\nDefault timeout: 300 seconds (configurable via INGEST_ENDPOINT_TIMEOUT_SECONDS and QUERY_ENDPOINT_TIMEOUT_SECONDS)"
    )
    print(
        "For testing, set INGEST_ENDPOINT_TIMEOUT_SECONDS=5 and QUERY_ENDPOINT_TIMEOUT_SECONDS=5 in .env and restart server."
    )
    print()

    # IMPORTANT: Replace this with a session_id that has indexed documents
    # You can find available session_ids by checking your Qdrant collection
    # or by ingesting a PDF first
    
    # Use the session_id from your collection logs:
    session_id = UUID("04ab7ffe-1e89-4e2a-a2da-0be16476c8b3")
    
    print(f"Using session_id: {session_id}\n")

    start = time.time()

    # Send a query that will take longer than the timeout
    # Using a larger top_k to make the request slower
    with httpx.Client(timeout=60.0) as client:
        try:
            response = client.post(
                f"{BASE_URL}/query/",
                params={
                    "query": "Analyze everything in this document in extreme detail",
                    "session_id": str(session_id),
                    "top_k": 10,
                },
                headers=HEADERS,
            )
            elapsed = time.time() - start

            print(f"Elapsed time: {elapsed:.2f}s")
            print(f"Status: {response.status_code}")

            if response.status_code == 504:
                print("\n[PASS] Timeout working correctly!")
                try:
                    print(f"Response: {response.json()}")
                except Exception:
                    print(f"Response: {response.text}")
            elif response.status_code == 200:
                print("\n[INFO] Request completed successfully (no timeout)")
                print("This means either:")
                print(
                    "  - The request was fast enough to complete within timeout"
                )
                print(
                    "  - INGEST_ENDPOINT_TIMEOUT_SECONDS or QUERY_ENDPOINT_TIMEOUT_SECONDS is set too high for this test"
                )
            else:
                print(f"\n[INFO] Received status {response.status_code}")
                try:
                    print(f"Response: {response.json()}")
                except Exception:
                    print(f"Response: {response.text}")

        except httpx.TimeoutException:
            elapsed = time.time() - start
            print(f"Elapsed time: {elapsed:.2f}s")
            print("\n[INFO] Client timed out before server response")
            print("Increase client timeout or decrease INGEST_ENDPOINT_TIMEOUT_SECONDS or QUERY_ENDPOINT_TIMEOUT_SECONDS")
        except Exception as e:
            elapsed = time.time() - start
            print(f"Elapsed time: {elapsed:.2f}s")
            print(f"[ERROR] {e}")


def test_health_check():
    """Sanity check - health endpoint should not timeout"""
    print("\n" + "=" * 60)
    print("Sanity Check: Health Endpoint")
    print("=" * 60)

    start = time.time()
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.get(f"{BASE_URL}/health")
            elapsed = time.time() - start
            print(f"Elapsed time: {elapsed:.2f}s")
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                print("\n[PASS] Health check completed quickly")
            else:
                print(f"\n[INFO] Health check returned {response.status_code}")

        except Exception as e:
            print(f"[ERROR] {e}")


def main():
    print("\n" + "=" * 60)
    print("TIMEOUT TEST SUITE")
    print("=" * 60)
    print("\nIMPORTANT: For effective testing, configure these in .env:")
    print("  INGEST_ENDPOINT_TIMEOUT_SECONDS=5")
    print("  QUERY_ENDPOINT_TIMEOUT_SECONDS=5")
    print("\nThen restart the server before running this test.")
    print()

    test_health_check()
    test_timeout()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    print("\nCheck server logs for timeout warnings:")
    print('  "Request timeout | path=/query/ | timeout_seconds=5"')


if __name__ == "__main__":
    main()
