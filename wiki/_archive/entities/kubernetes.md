# Kubernetes

**Type**: Platform / Tool
**Category**: Container Orchestration & Scaling
**Role in Architecture**: Implementation layer (production deployment)

---

## Overview

Kubernetes is the open-source standard for orchestrating containerized applications at scale. It automates deployment, scaling, and management of underwriting service containers.

**Key Characteristics**:
- **Declarative**: Describe desired state (YAML files), Kubernetes maintains it
- **Self-Healing**: Automatically restarts failed containers
- **Auto-Scaling**: Horizontal Pod Autoscaler (HPA) scales based on CPU/memory/custom metrics
- **Rolling Updates**: Zero-downtime deployments of new versions

---

## Why Kubernetes for Insurance Underwriting

### Use Case: Scaling Underwriting to Production

**Scenario**:
- Monday morning: 50 underwriting cases arrive
- Wednesday: 500 cases (customer campaign launched)
- Friday: Back to 50 cases

**With Kubernetes**:
- **Low demand**: 3 API pods, 5 worker pods
- **High demand**: Automatically scales to 10 API pods, 25 worker pods
- **Auto-scaling rule**: Scale up if queue depth > 100, scale down if idle

**Benefits**:
- Cost efficient (don't pay for unused capacity)
- Handles traffic spikes gracefully
- Self-healing (if a pod crashes, Kubernetes restarts it)

---

## Kubernetes Architecture for Underwriting

### Cluster Components

```
┌─ Kubernetes Cluster ──────────────────────────┐
│                                                 │
│  ┌─ API Server ─┐  ┌─ API Server ──┐         │
│  │  FastAPI     │  │  FastAPI      │ (HPA)   │
│  │  Port 8000   │  │  Port 8000    │ scales  │
│  └──────────────┘  └───────────────┘         │
│         ↓                 ↓                    │
│  ┌──────── Redis ─────────┐                  │
│  │  Message Broker        │                  │
│  │  (Celery Queue)        │                  │
│  └────────────────────────┘                  │
│         ↑         ↑          ↑                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │   │
│  │ (Celery) │  │ (Celery) │  │ (Celery) │   │
│  └──────────┘  └──────────┘  └──────────┘   │
│                     (HPA scales 1-25 pods)   │
│         ↓         ↓          ↓                │
│  ┌────────── PostgreSQL ──────────┐          │
│  │  Case History & Audit Trail    │          │
│  └────────────────────────────────┘          │
│         ↓                                      │
│  ┌────────── Persistent Volume ───────┐      │
│  │  Medical PDFs, Extracted JSON      │      │
│  └────────────────────────────────────┘      │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Deployment Manifests

**API Server Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: underwriting-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: underwriting-api
  template:
    metadata:
      labels:
        app: underwriting-api
    spec:
      containers:
      - name: api
        image: underwriting-service:1.2.3
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
          limits:
            cpu: "500m"
            memory: "1Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: underwriting-api
spec:
  selector:
    app: underwriting-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: underwriting-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: underwriting-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**Worker Deployment** (scales 1-25 based on queue depth):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: worker
        image: underwriting-service:1.2.3
        command: ["celery", "-A", "tasks", "worker"]
        env:
        - name: CELERY_BROKER_URL
          value: "redis://redis:6379"
        resources:
          requests:
            cpu: "500m"
            memory: "1Gi"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: celery-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: celery-worker
  minReplicas: 1
  maxReplicas: 25
  metrics:
  - type: Pods
    pods:
      metricName: celery_queue_length
      targetAverageValue: "10"
```

---

## Key Kubernetes Concepts

### Pods
Smallest unit; wraps a container (usually one container per pod)

### Deployments
Manage replica sets; enable rolling updates and rollbacks

### Services
Expose pods internally or externally (IP discovery, load balancing)

### Persistent Volumes (PV) & Claims (PVC)
Storage that survives pod restarts (for medical PDFs, audit logs)

### Secrets
Store sensitive data (database passwords, API keys) safely

### ConfigMaps
Store non-sensitive configuration (feature flags, log levels)

### Ingress
External HTTP/HTTPS routing (maps domain.com → service)

---

## Operational Monitoring

### Key Metrics to Track
- **Pod Resource Usage**: CPU, memory (ensure no OOM kills)
- **Queue Depth**: How many pending documents to process
- **Task Latency**: P50, P95, P99 percentiles for scoring
- **Error Rate**: Failed document extractions, scoring failures

### Tools
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **AlertManager**: Paging on-call engineer for production incidents

---

## Cost Optimization

**Dev/Test** (low scale):
- 1 API pod, 1 worker pod
- Costs ~$30/month on AWS EKS

**Production** (with auto-scaling):
- 3-10 API pods, 1-25 worker pods
- Average cost ~$200/month, scales up temporarily

**Off-Hours** (cost reduction):
- Scale to 0 pods during nights/weekends
- Saves 50% of monthly costs

---

## Resources

- **Kubernetes Documentation**: https://kubernetes.io/docs/concepts/overview/
- **Best Practices**: Rolling updates, resource requests, health checks

---

## Related Technologies

- [FastAPI](./fastapi.md) — API application running in Kubernetes
- [Celery](./celery.md) — Worker processes orchestrated by Kubernetes
- Docker — Containerization (not yet documented)

## Related Topics

- [Operational Architecture & Deployment](../topics/operational-architecture.md) — Full deployment context

---

## Last Updated
2026-04-09
