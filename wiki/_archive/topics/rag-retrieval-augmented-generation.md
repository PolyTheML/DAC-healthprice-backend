# RAG: Retrieval-Augmented Generation

**Last Updated**: 2026-04-09

## Overview

RAG augments LLM responses with retrieved context from a knowledge base. For insurance, this means grounding underwriting decisions in relevant medical literature, actuarial precedents, and company guidelines.

---

## Why RAG for Insurance Underwriting

- **Grounding**: Decisions are backed by explicit sources (medical guidelines, actuarial tables)
- **Consistency**: Same questions always reference the same knowledge base
- **Auditability**: Can trace decision reasoning to source documents
- **Reduced hallucination**: LLM doesn't invent medical facts; it retrieves them

---

## LlamaIndex: End-to-End RAG Platform

**Source**: [LlamaIndex Docs](https://developers.llamaindex.ai/python/framework/)

### Four-Layer Architecture

1. **Data Ingestion** — Read from PDFs, APIs, databases
2. **Indexing** — Create vector embeddings + metadata indices
3. **Querying** — Retrieve relevant context + generate responses
4. **Agents** — Multi-step reasoning with tool use

### Basic RAG in 5 Lines

```python
documents = SimpleDirectoryReader("medical_guidelines").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("What is treatment for hypertension?")
```

### LlamaParse: VLM-Powered Document Parsing

- Handles tables, charts, embedded images
- Supports multiple languages
- Preserves document structure for better retrieval

---

## Vector Databases for RAG

### Weaviate

**Source**: [Weaviate Docs](https://docs.weaviate.io/weaviate)

- **Graph + vector search**: Combines semantic similarity with relationship queries
- **Built-in MLOps**: Model management, versioning, A/B testing
- **Scaling**: Cloud-native, auto-sharding
- **Cost**: Enterprise option with pay-as-you-go

### Other Options

| DB | Strength | Best For |
|----|----------|----------|
| **Chroma** | Simple, Python-native | Prototyping |
| **Pinecone** | Managed, serverless | Production without ops |
| **Milvus** | Open-source, scalable | Self-hosted production |
| **Qdrant** | Fast, small footprint | Edge deployments |

---

## Insurance Knowledge Base Structure

### Example: Hypertension Guidelines

```
Document: WHO Hypertension Guidelines 2023
Chunks:
  1. Definition: SBP ≥140 OR DBP ≥90
  2. Risk stratification: Stage 1 (140-159), Stage 2 (≥160)
  3. Treatment options: Lifestyle (first), pharmacological if...
  4. Monitoring: Annual follow-up for Stage 1, quarterly for Stage 2

Metadata:
  - source: WHO
  - date: 2023
  - domain: hypertension
  - authority_level: high
```

When processing an applicant with Stage 1 hypertension, RAG retrieves WHO guidance → LLM contextualizes within underwriting rules.

---

## LangChain: RAG + Agents

**Source**: [LangChain Docs](https://python.langchain.com/docs/use_cases/question_answering/)

### Pattern: RAG + Tool Use

```python
# Build retriever from knowledge base
retriever = vectorstore.as_retriever()

# Create agent with retriever as tool
tools = [
    Tool(name="MedicalGuidelines", func=retriever.retrieve),
    Tool(name="ActuarialTables", func=actuarial_db.query)
]

agent = AgentExecutor.from_agent_and_tools(...)
```

Underwriting agent can now:
- ✅ Retrieve medical context for the applicant's condition
- ✅ Look up actuarial tables for risk scoring
- ✅ Cross-reference with company policies
- ✅ Provide sources for every decision

---

## Hybrid Search (Vector + Keyword)

Many RAG systems use **hybrid retrieval**:

1. **Vector search** (semantic similarity) — "Find documents about cardiovascular risk"
2. **Keyword search** (BM25) — "Find documents mentioning 'myocardial infarction'"
3. **Fusion** — Rank results by both signals

Improves recall for rare conditions and specific terminology.

---

## Related Topics

- [Intelligent Document Processing](./intelligent-document-processing.md) — Extracting medical data from PDFs
- [Medical Data Validation](./medical-data-validation.md) — Ensuring retrieved data is accurate
- [Agent Orchestration](./agent-orchestration.md) — Agents using RAG for decision-making
