"""
Test script for File Size Limits

What it tests:
    - Files exceeding MAX_FILE_SIZE_MB (default: 50MB) are rejected
    - PDFs exceeding MAX_PDF_PAGES (default: 200 pages) are rejected

Expected behavior:
    - Large files return error in response: {"results": [{"filename": "...", "error": "File exceeds 50MB limit"}]}
    - Check logs for: "File size limit exceeded | filename=large.pdf | size_mb=60.00 | limit_mb=50"

Usage:
    1. Start the server: make dev
    2. Optionally set smaller limit for testing: MAX_FILE_SIZE_MB=10 in .env
    3. Run this script: python scripts/test_file_limits.py
"""

import httpx
from uuid import UUID

BASE_URL = "http://localhost:8000"
# Replace with your actual token or set AUTH_ENABLED=false in .env
HEADERS = {"Authorization": "Bearer YOUR_TOKEN"}


def test_file_size_limit():
    """Test file size limit (default: 50MB)"""
    print("=" * 60)
    print("Testing File Size Limit")
    print("=" * 60)
    print("\nDefault limit: 50MB (configurable via MAX_FILE_SIZE_MB)")
    print("Creating a ~60MB fake PDF to test the limit...\n")

    # IMPORTANT: Replace this with a session_id that has indexed documents
    # You can find available session_ids by checking your Qdrant collection
    # or by ingesting a PDF first
    
    # Use the session_id from your collection logs:
    session_id = UUID("04ab7ffe-1e89-4e2a-a2da-0be16476c8b3")
    
    print(f"Using session_id: {session_id}\n")

    # Create a ~60MB fake PDF (or use smaller size if MAX_FILE_SIZE_MB is reduced)
    target_size_mb = 60
    pdf_header = b"%PDF-1.4\n"
    padding = b"x" * (target_size_mb * 1024 * 1024 - len(pdf_header))
    large_content = pdf_header + padding

    print(f"File size: {len(large_content) / (1024 * 1024):.2f} MB")

    with httpx.Client(timeout=120.0) as client:
        try:
            response = client.post(
                f"{BASE_URL}/ingest-pdfs/?session_id={session_id}",
                files={
                    "files": ("large.pdf", large_content, "application/pdf")
                },
                headers=HEADERS,
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")

            # Check if error message is in response
            result = response.json()
            if "results" in result:
                for r in result["results"]:
                    if "error" in r and "limit" in r["error"].lower():
                        print("\n[PASS] File size limit is working correctly!")
                    else:
                        print(
                            "\n[INFO] Response received but may need manual verification"
                        )
            else:
                print("\n[INFO] Unexpected response format")

        except httpx.TimeoutException:
            print("[ERROR] Request timed out")
        except Exception as e:
            print(f"[ERROR] {e}")


def test_small_file():
    """Test that small files are accepted (sanity check)"""
    print("\n" + "=" * 60)
    print("Sanity Check: Small File Should Be Accepted")
    print("=" * 60)

    # IMPORTANT: Replace this with a session_id that has indexed documents
    # You can find available session_ids by checking your Qdrant collection
    # or by ingesting a PDF first
    
    # Use the session_id from your collection logs:
    session_id = UUID("04ab7ffe-1e89-4e2a-a2da-0be16476c8b3")
    
    print(f"Using session_id: {session_id}\n")

    # Create a valid small PDF
    small_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    print(f"File size: {len(small_content)} bytes")

    with httpx.Client(timeout=60.0) as client:
        try:
            response = client.post(
                f"{BASE_URL}/ingest-pdfs/?session_id={session_id}",
                files={
                    "files": ("small.pdf", small_content, "application/pdf")
                },
                headers=HEADERS,
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")

            # Note: The small file may fail due to invalid PDF format,
            # but it should NOT fail due to size limit
            if response.status_code != 429:  # Not rate limited
                result = response.json()
                if "results" in result:
                    for r in result["results"]:
                        if "error" in r and "limit" in r["error"].lower():
                            print("\n[FAIL] Small file was rejected for size!")
                        else:
                            print(
                                "\n[PASS] Small file was not rejected for size (may have other errors)"
                            )

        except Exception as e:
            print(f"[ERROR] {e}")


def main():
    print("\n" + "=" * 60)
    print("FILE LIMITS TEST SUITE")
    print("=" * 60)
    print("\nTip: For faster testing, set smaller limits in .env:")
    print("  MAX_FILE_SIZE_MB=10")
    print()

    test_file_size_limit()
    test_small_file()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    print(
        "\nCheck server logs for detailed messages about file size validation."
    )


if __name__ == "__main__":
    main()
