# Celery

**Type**: Framework / Tool
**Category**: Asynchronous Task Processing
**Role in Architecture**: Implementation layer (background task queue)

---

## Overview

Celery is a distributed task queue library for Python that handles asynchronous processing of long-running jobs (document parsing, model inference, medical data extraction).

**Key Characteristics**:
- **Distributed**: Workers can run on separate machines
- **Reliable**: Automatic retries, task persistence
- **Flexible**: Supports multiple message brokers (Redis, RabbitMQ)
- **Monitoring**: Flower UI for task monitoring and stats

---

## Why Celery for Medical Document Processing

### Use Case: Heavy I/O Processing

**Problem**: Medical PDF parsing can take 30-60 seconds. If handled synchronously in FastAPI:
- User sees spinning wheel for 60 seconds
- API server memory is blocked
- Can't handle concurrent requests efficiently

**Solution with Celery**:

```python
# FastAPI endpoint (fast, returns immediately)
@app.post("/api/underwriting/submit")
async def submit_case(case_id: str, pdf_file: UploadFile):
    # Save file to storage
    # Queue async task
    extract_medical_data.delay(case_id, pdf_path)
    return {"case_id": case_id, "status": "processing"}

# Celery worker (runs in background)
@celery_app.task
def extract_medical_data(case_id: str, pdf_path: str):
    # Takes 30-60 seconds
    medical_data = parser.extract(pdf_path)
    # Update database
    db.update_case(case_id, extracted_data=medical_data)
    # Trigger next task: risk scoring
    score_risk.delay(case_id)
```

**Benefits for Insurance**:
- Underwriter submits 100 cases rapidly (no wait)
- Workers process 100 PDFs in parallel (if you have 10 workers, each processes 10)
- Each case is scored independently
- Failures in one case don't affect others

---

## Architecture Integration

### Task Flow for Underwriting

```
1. [FastAPI POST /submit] → Queue task "extract_medical_data"
2. [Celery Worker 1] ← Consume task, extract PDF → Update DB
3. [Trigger next task] → Queue task "score_risk"
4. [Celery Worker 2] ← Consume task, calculate GLM → Update DB
5. [Trigger next task] → If score > threshold, queue "route_to_human"
6. [Underwriter Dashboard] ← Pulls cases requiring review (via API)
```

### Task Queues & Routing

Different task types can be routed to different worker pools:

| Queue | Task | Worker Count | Timeout |
|-------|------|--------------|---------|
| `intake` | extract_medical_data, parse_pdf | 5 workers | 120s |
| `scoring` | score_risk, calculate_premium | 3 workers | 60s |
| `alerts` | notify_underwriter, send_email | 1 worker | 30s |

---

## Production Setup

### Message Broker Options
- **Redis**: Simple, in-memory, good for < 100k tasks/day
- **RabbitMQ**: Enterprise-grade, better for > 100k tasks/day

### Monitoring
- **Flower**: Web UI showing active tasks, task history, worker stats
- **Dead Letter Queues**: Failed tasks that need investigation

### Deployment (Kubernetes)

```yaml
# Celery worker deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker-intake
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: worker
        image: underwriting-service:latest
        command: ["celery", "-A", "tasks", "worker", "-Q", "intake"]
        resources:
          requests:
            cpu: "500m"
            memory: "1Gi"
```

---

## Resources

- **Celery Documentation**: https://docs.celeryq.dev/en/stable/
- **Best Practices**: Reliable task processing, retries, dead-letter handling

---

## Related Technologies

- [FastAPI](./fastapi.md) — REST API framework that queues tasks to Celery
- [Kubernetes](./kubernetes.md) — Orchestrates worker pods
- **Redis** — Message broker (external infrastructure, not yet documented)

## Related Topics

- [Operational Architecture & Deployment](../topics/operational-architecture.md) — Full deployment context

---

## Last Updated
2026-04-09
