# Lesson 6: Production Deployment on AWS — Event-Driven Serverless Architecture

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md)

## From Local to Cloud

**Lessons 1-5** built a RAG system locally:
- Notebook-based (convenient for prototyping)
- Local storage (ChromaDB on disk)
- Manual document upload
- Single-user interaction

**Lesson 6** shows how to scale to production:
- Automatic document processing (event-driven)
- Cloud storage (S3)
- Cloud embeddings (Bedrock)
- Cloud search (Bedrock Knowledge Base)
- Multi-user agents (Strands Agents + memory)

---

## The Paradigm Shift: Event-Driven Architecture

### What Is Event-Driven Architecture?

**Traditional (polling)**:
```
Script runs every 5 minutes:
  1. Check S3: "Is there a new file?"
  2. If yes, process it
  3. If no, wait 5 minutes and check again
```

**Event-driven** (push notification):
```
S3: "A file just arrived!"
  → EventBridge: "Routing this event..."
  → Lambda: "I heard! Processing now..."
  → (No polling, no wasted compute)
```

### Benefits

1. **Efficiency**: Pay only when documents arrive, not for idle checking
2. **Responsiveness**: Start processing milliseconds after file upload
3. **Scalability**: Automatically handle 1 file/day or 1000 files/hour
4. **Decoupling**: Components don't know about each other; they just emit/listen to events

---

## Core AWS Services

### 1. Amazon S3 (Simple Storage Service)

**Role**: Central repository for all data (input, output, knowledge base source)

**Architecture for DAC-UW**:
```
S3 Bucket: dac-uw-documents
├── input/
│   ├── identity/
│   ├── medical/
│   ├── financial/
│   └── claims/
├── output/
│   ├── identity-chunks/
│   ├── medical-chunks/
│   ├── financial-chunks/
│   └── claims-chunks/
└── archives/
    └── [processed documents]
```

**Events S3 emits**:
- Object created (file uploaded)
- Object deleted
- Object restored (from archive)

**Why S3**:
- Infinitely scalable
- Pay per GB stored, not per file
- Fine-grained access control (IAM)
- Integrates with every AWS service
- Can host static website (policy docs, UI)

### 2. AWS Lambda (Serverless Compute)

**Role**: Runs ADE parser when documents arrive

**What happens**:
1. S3 emits: "New file uploaded: `identity/passport.pdf`"
2. Lambda function wakes up (auto-provisioned by AWS)
3. Code runs:
   - Download `passport.pdf` from S3
   - Call ADE API to parse
   - Save output to S3 `output/identity-chunks/`
4. Lambda stops (no running cost)
5. You pay only for execution time (milliseconds)

**Why Lambda**:
- No server to manage (AWS patches, scales, monitors)
- Pay per 100ms of execution
- Automatic scaling (10 concurrent → 10,000 concurrent = AWS handles it)
- Rapid iteration (edit code, redeploy in seconds)

**Limitations**:
- 15-minute timeout (okay for document parsing; okay for ADE)
- Cold starts (first invocation ~1-2s overhead)
- Memory/CPU linked (pick memory; CPU scales proportionally)

### 3. AWS EventBridge (Event Router)

**Role**: Routes S3 events to Lambda

**How it works**:
```
Rule: "If file uploaded to input/medical/ → invoke Lambda with document type = medical"
```

**Why not just S3 → Lambda direct?**
- EventBridge adds filtering and routing
- Can route same event to multiple targets
- Can retry on failure
- Can delay/batch events

### 4. IAM (Identity & Access Management)

**Role**: Control who/what can access resources

**Key concepts**:
- **Role**: Identity (e.g., "Lambda document processor")
- **Policy**: Permissions (e.g., "can read from S3 input, write to S3 output")

**For Lambda document processor**:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",      // Read files from input/
    "s3:PutObject",      // Write files to output/
    "s3:HeadObject",     // Check if file exists
    "logs:*"             // Write CloudWatch logs for debugging
  ],
  "Resource": "arn:aws:s3:::dac-uw-documents/*"
}
```

### 5. Amazon Bedrock (Managed LLM Service)

**Role**: Two parts:

#### A. Bedrock Knowledge Base
- Stores vector embeddings
- Provides semantic search
- Uses Amazon Titan for embeddings
- Uses OpenSearch Serverless for vector storage
- Auto-scales (no provisioning)

**Data flow**:
```
S3 output/medical-chunks/ [JSON files]
          ↓
Bedrock Knowledge Base [ingest job]
          ↓
OpenSearch [stores vectors]
          ↓
[Ready for search]
```

#### B. Bedrock Runtime (LLM Access)
- Provides Claude, Nova, other foundation models
- Bedrock handles scaling, throughput, availability
- You call it like an API

### 6. Bedrock AgentCore Memory

**Role**: Provides three types of long-term memory:

1. **Summary Memory**: Summarizes past conversations
   - "User mentioned they prefer short answers"
2. **Semantic Memory**: Stores facts
   - "User has diabetes (relevant for health queries)"
3. **User Preference**: Learns preferences
   - "User prefers concise responses, numbered lists"

**Why it matters**: Agent remembers context across sessions, feels more like a real assistant.

### 7. Strands Agents (Open-Source Framework)

**Role**: High-level abstraction for building agents

**What it does**:
- Defines agent behavior (system prompt, tools, memory)
- Handles tool-calling loop (agent decides which tool to use)
- Integrates with AWS (Bedrock, S3, Knowledge Base)
- Production-ready logging, tracing

**Example**:
```python
agent = Agent(
  name="medical_insurance_bot",
  model="claude-opus-4-6",  # via Bedrock
  system_prompt="You are a medical insurance underwriting assistant...",
  tools=[
    search_knowledge_base,  # Custom tool
    calculate_risk_score,   # Custom tool
  ],
  memory=agent_memory,  # AgentCore Memory
)

response = agent.invoke(
  input="Does the applicant have pre-existing conditions?",
  actor_id="underwriter_123",  # For personalization
  session_id="case_456"  # For conversation context
)
```

---

## The Complete Pipeline

### High-Level Flow

```
User uploads PDF to S3 input/medical/
    ↓
S3 triggers Lambda (via EventBridge)
    ↓
Lambda downloads PDF
    ↓
Lambda calls ADE API to parse
    ↓
Lambda saves to S3 output/medical-chunks/
    ↓
Bedrock Knowledge Base ingests chunks
    ↓
User asks agent a question
    ↓
Agent calls search_knowledge_base tool
    ↓
Bedrock Knowledge Base searches vectors
    ↓
Agent receives chunk + visual grounding
    ↓
Agent asks LLM to synthesize answer
    ↓
Agent returns: Answer + Source + Visual proof
```

### Detailed Data Flow (with Grounding)

When user asks "Does applicant have hypertension?":

1. **Agent receives query**
2. **Calls search tool** with query
3. **Knowledge Base retrieves**:
   - Top-K similar chunks
   - Chunk metadata (page, bbox, type)
4. **Agent verifies**:
   - Checks if source is from medical_chunks/
   - Parses metadata to get original bbox
5. **Generates grounding image**:
   - Crops PDF page using bbox
   - Uploads to S3 (presigned URL)
6. **LLM generates answer**:
   - "Yes, applicant has hypertension (Stage 2 per page 3, Table 1)"
   - Includes URL to cropped image
7. **User can verify**:
   - Click URL → see cropped table
   - Verify answer matches source

---

## Serverless Philosophy

**Serverless ≠ "No servers"** (there are servers, you just don't manage them)

**Serverless = Three properties**:

1. **No infrastructure management**
   - AWS provisions, patches, scales servers
   - You just write code

2. **Auto-scaling**
   - 1 document → 1 Lambda
   - 1000 documents → 1000 parallel Lambdas
   - Automatic; no configuration needed

3. **Pay-per-use**
   - Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
   - S3: $0.023 per GB stored
   - Bedrock: $0.00075 per page parsed, $0.00001 per embedding
   - No charge for idle time

**For DAC-UW**: Cost scales with volume. 1000 documents/month = low cost. 100K documents/month = higher cost but still automatic scaling.

---

## Compared to Local Setup (Lessons 1-5)

| Aspect | Local (Lesson 5) | AWS Production (Lesson 6) |
|--------|------------------|--------------------------|
| **Storage** | Disk on laptop | S3 (unlimited) |
| **Compute** | Your CPU | Lambda (auto-scale) |
| **Embeddings** | OpenAI API | Bedrock (managed) |
| **Vector DB** | ChromaDB (local) | Bedrock Knowledge Base |
| **Agents** | LangChain | Strands Agents |
| **Memory** | None (one session) | AgentCore Memory (persistent) |
| **Users** | 1 (you) | Many (concurrent) |
| **Cost** | Free (API calls) | Per-use billing |
| **Uptime** | When laptop is on | 99.99% AWS SLA |

---

## Deployment Steps (Lesson 6 Lab)

1. **Package Lambda code** (Python + dependencies)
2. **Create IAM role** (permissions for Lambda)
3. **Deploy Lambda** to AWS
4. **Set up S3 trigger** (invoke Lambda on file upload)
5. **Upload test documents** to S3 input/
6. **Monitor CloudWatch logs** (watch Lambda execute)
7. **Verify output** in S3 output/
8. **Ingest to Knowledge Base** (one-time or continuous)
9. **Build Strands Agent** (with search tool + memory)
10. **Test agent** (ask questions, see visual grounding)

---

## Relevance to DAC-UW: Path to Production

**Current state** (if using local RAG):
- Manual document upload
- Notebook-based (not for users)
- No history/memory
- Limited to dev machine

**With AWS deployment**:
- Underwriters upload documents to S3 (via web UI or S3 client)
- Lambda automatically extracts
- Knowledge Base indexes
- Underwriting agent answers questions with visual proof
- All history tracked (compliance)
- Scales from 10 to 100K documents

**Compliance advantages**:
- Audit trail (who uploaded what, when)
- Visual grounding (where answers came from)
- Bedrock encryption (documents protected in transit + at rest)
- IAM access control (role-based permissions)

---

## See Also

- [AWS](../entities/aws.md) — Cloud infrastructure overview
- [Strands Agents](../entities/strands-agents.md) — Agent framework for AWS deployment
- [Document AI Course](../sources/2026-04-10_document-ai-course.md) — Full course reference
