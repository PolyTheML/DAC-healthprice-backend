# Lesson 5: RAG for Document Understanding — Embedding, Search, & Grounding

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md)

## The RAG Paradigm

**RAG = Retrieval-Augmented Generation**

**Core idea**: Instead of asking an LLM to answer from its training data (prone to hallucination), *retrieve relevant context first*, then ask the LLM to answer based on that context.

```
Naive LLM:
  Question: "What was Apple's net sales in 2023?"
  → LLM guess from training data (possibly outdated, hallucinated)

RAG System:
  Question: "What was Apple's net sales in 2023?"
  → Search documents for "net sales 2023"
  → Retrieve exact table from 10-K filing
  → LLM: "Based on this table, net sales were $383 billion"
  → Include link to table as proof
```

---

## Why RAG Matters for Regulated Industries

In **regulated industries** (finance, healthcare, insurance), decisions must be:
1. **Accurate** (wrong answer costs money, harms people)
2. **Defensible** (can you explain where the answer came from?)
3. **Auditable** (regulators can verify the decision)

**RAG solves this** by making the decision chain transparent:

```
Question → Retrieval (with evidence) → Generation (grounded) → Answer + Proof
```

**Compare**:
- ❌ Pure LLM: "Net sales were $383B" (how do you know? where's your source?)
- ✅ RAG: "Net sales were $383B per page 28, table 3, row 5" (auditable)

---

## The RAG Pipeline (6 Steps)

### Phase 1: Preprocessing

#### Step 1: Parsing
Parse documents into clean, structured text.

**Why this matters**: If you feed RAG garbage OCR output, retrieval will search garbage, and generation will hallucinate.

**Good parsing** (from ADE):
- Clean markdown tables (not jumbled text)
- Correct reading order (not columns mixed)
- Chunk boundaries (tables are single chunks, not scattered rows)

**Bad parsing** (from naive OCR):
- Table becomes: "Revenue 2023 $100M Q1 $50M Q2" (no structure)
- Multi-column doc: "Title Abstract Introduction Middle of left column Introduction middle of right" (scrambled)

#### Step 2: Embedding
Convert each chunk of text into a **vector** (list of numbers) that captures semantic meaning.

**Example**:
- "Apple's net sales in fiscal 2023" → [0.12, -0.34, 0.98, ...] (1536 numbers)
- "Revenue in 2023" → [0.11, -0.35, 0.97, ...] (similar vector)
- "Capital expenditure" → [-0.45, 0.22, 0.12, ...] (different vector)

**Why vectors work**: Mathematically similar vectors mean semantically similar meanings. You can measure similarity with distance.

**Model**: OpenAI's Text-Embedding-3-Small (produces 1536-dimensional vectors).

#### Step 3: Storage
Store vectors in a **vector database** (ChromaDB for local, Bedrock Knowledge Base for AWS).

**Indexing**: Databases use HNSW (Hierarchical Navigable Small World) algorithm for fast nearest-neighbor search.

**Metadata**: Store alongside vectors:
- `chunk_id` (link to original document)
- `chunk_type` (table, figure, text)
- `page` (page number)
- `bbox` (bounding box for visual grounding)

### Phase 2: Retrieval

#### Step 4: Query Embedding
User asks a question. Convert question to vector using same embedding model.

**Example**: "What were Apple's net sales in 2023?" → [0.13, -0.33, 0.99, ...]

#### Step 5: Search
Find top-K vectors in database closest to query vector.

**Metric**: Similarity = 1 - distance. Higher = better match.

**Filtering**: Remove results below similarity threshold (e.g., only keep matches > 0.7 confidence).

#### Step 6: Formatting
Display retrieved chunks with:
- Relevance score (how similar is this to the question?)
- Source info (page, chunk type, chunk_id)
- Visual grounding (show cropped image from original PDF)

### Phase 3: Generation

#### Step 7: Prompt Construction
Combine question + retrieved context into a prompt:

```
System: You are a document analyst. Answer based only on the provided context.

Context:
[Retrieved chunk 1]
[Retrieved chunk 2]
[Retrieved chunk 3]

Question: What were Apple's net sales in 2023?

Answer: Based on the context provided, ...
```

#### Step 8: LLM Generation
LLM reads the prompt and generates answer grounded in context.

**Why safe**: LLM can't hallucinate about facts not in the context. If answer isn't in documents, LLM should say so.

---

## Why Semantic Search > Keyword Search

**Naive keyword search** (traditional search engines):
- Query: "net sales 2023"
- Search for exact string match
- Problem: What if document says "revenue in fiscal 2023"? Misses it.

**Semantic search** (RAG with embeddings):
- Query: "net sales 2023"
- Convert to vector
- Find similar vectors regardless of exact wording
- Finds: "revenue in fiscal 2023", "total sales for 2023", etc.

**Real example** (from Lesson 5):
- Question: "What helps with cold symptoms?"
- Naive search: Looks for "cold symptoms" string
- Semantic search: Finds "nasal congestion", "runny nose", "cough" (symptoms of cold)

---

## Visual Grounding: The Compliance Game-Changer

**The problem**: LLM says "net sales were $383B" but doesn't cite source. How do you verify?

**Visual grounding** (enabled by ADE + RAG):
1. Every retrieved chunk has `bbox` (bounding box on original page)
2. System generates a **cropped image** of that region
3. User can see exactly which part of which page provided the answer

**Why crucial for regulated industries**:
- **Compliance**: Auditor asks "where did you get this number?" You show them the table.
- **Trust**: System shows its work; humans can verify.
- **Error correction**: If retrieved chunk is wrong, easy to spot and fix.
- **Liability**: Documented decision trail.

---

## Chunk-Level vs. Page-Level Trade-offs

When embedding, two strategies:

### Chunk-Level Embedding
Embed each distinct piece of content separately (paragraph, table row, figure caption).

**Pros**:
- Precise retrieval (exact paragraph matching)
- Better for complex documents
- Can ground to specific table cells

**Cons**:
- More embeddings to store (1000s per document)
- Slightly slower database

### Page-Level Embedding
Embed entire page as one chunk.

**Pros**:
- Fewer vectors to manage
- Faster database operations
- Simpler implementation

**Cons**:
- Less precise (might retrieve whole page when only one table relevant)
- Harder to ground to specific region

**For DAC-UW**: Chunk-level better. Insurance documents are often dense with multiple forms/tables per page; precise retrieval matters.

---

## Relevance to DAC-UW: Multi-Document Case

Imagine underwriting a large commercial insurance claim. You have:
1. Financial statements (3 years, multi-page)
2. Tax returns (3 years)
3. Bank statements (6 months)
4. Applicant ID documents
5. Medical records

**Question**: "What is the applicant's total assets?"

**RAG approach**:
1. Parse all documents with ADE
2. Embed all chunks (roughly 500-1000 across all docs)
3. Store in vector DB with metadata (document type, page, chunk_id)
4. Query: "What is the applicant's total assets?"
5. Retrieve: Chunks from bank statements, investment accounts, real estate declarations
6. LLM synthesizes: "Total assets are $2.5M: $1.2M in bank accounts (page 3), $1M in investments (page 7), $300K in real estate (page 12)"
7. Visual proof: Show user the three pages

**Why this beats manual review**:
- Automatically aggregates across documents
- Sources cited (auditable)
- Visual proof included
- No human has to manually flip through 50 pages

---

## Limitations & When RAG Breaks

RAG works best for **lookup + synthesis** questions.

**Good questions**:
- "What was revenue in 2023?" (exact lookup)
- "How did revenue trend 2022-2023?" (compare retrieved chunks)
- "What are the risks listed?" (aggregate across pages)

**Hard questions**:
- "Is this applicant a good insurance risk?" (requires domain reasoning, risk assessment)
- "Should we approve this claim?" (requires policy knowledge, decision logic)
- "What's missing from this application?" (requires knowledge of all possible required docs)

**Why**: RAG can't reason about things not explicitly in documents. For business decisions, you still need:
- Domain expert (underwriter)
- Policy rules (decision engine)
- Risk models (pricing)

**Solution for DAC-UW**: RAG for *information extraction*; underwriting rules for *decision-making*.

---

## See Also

- [RAG: Retrieval-Augmented Generation](./rag-retrieval-augmented-generation.md) — Broader RAG concepts
- [Document AI Course](../sources/2026-04-10_document-ai-course.md) — Full course reference
- [Visual Grounding](./visual-grounding.md)
- [Lesson 6: Production Deployment on AWS](./lesson-6-production-aws-deployment.md)
