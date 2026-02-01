# TODOs

## Critical (Must-Do Before Production)

- [ ] Make query use any Anthropic model (currently hard-coded)
- [ ] Add model semaphore - ColQwen2.5 has no synchronization; 50 concurrent requests = race conditions/OOM
- [ ] Add memory limits - Entire PDFs loaded at once; no cleanup between requests
- [ ] Add rate limiting - No request throttling; one heavy request can starve others
- [ ] Add file size limits - No validation; large PDFs cause memory explosion
- [ ] Add request timeouts - PDF conversion, model inference, network calls can hang forever
- [ ] Use worker pooling - Single uvicorn worker insufficient for 50 users (use Gunicorn + workers)

## High Priority

- [ ] Add request queuing for ingestion - Use Celery/RQ to limit concurrent PDF processing
- [ ] Add connection pool limits for Supabase - Parallel uploads could spawn unlimited connections
- [ ] Add retry logic for Supabase uploads/downloads
- [ ] Add retry logic for Qdrant query operations (upserts already have retry)
- [ ] Add comprehensive timeout config (PDF: 300s, model: 120s, Qdrant: 30s, uploads: 60s)

## Medium Priority

- [ ] Add health check endpoints (Qdrant, Supabase, model responsiveness, memory)
- [ ] Add monitoring (queue depth, memory per request, response times, error rates)
- [ ] Stream PDF processing instead of loading entire file into memory
- [ ] Separate ingestion and query workers for better resource isolation

## Low Priority / Nice-to-Have

- [ ] Add partial success handling for batch ingestion (currently fails entirely if any file fails)
- [ ] Use numpy arrays instead of Python lists for embeddings (more memory efficient)
- [ ] Add connection warmup on startup
- [ ] Add backpressure for streaming responses (cleanup on client disconnect)
