# arxiv-sanity-lite: AI-Powered Paper Discovery from arXiv

**Source**: https://github.com/karpathy/arxiv-sanity-lite  
**Live Instance**: https://arxiv-sanity-lite.com  
**Type**: Web Application / Paper Recommendation System  
**Author**: Andrej Karpathy  
**Ingested**: 2026-04-10  
**Status**: Maintained, widely used by ML/AI researchers

---

## Executive Summary

**arxiv-sanity-lite** is a lightweight web application that transforms arXiv discovery from "overwhelming" to "curated." It polls arXiv's API daily for new papers, allows researchers to tag papers by interest, and uses machine learning to recommend related work—ensuring you never miss important papers in your field.

**Core Value**: Converts arXiv from a firehose (100+ papers/day in some categories) into a personalized feed of relevant research.

---

## How It Works

### Phase 1: Paper Collection (Automated)
**Daily**: arxiv-sanity-lite polls the arXiv API for new papers

```
arXiv API → New papers in Machine Learning, AI, NLP, etc.
            → arxiv-sanity-lite database
```

**Captures for each paper**:
- Title, authors, affiliation
- Abstract
- Subject classification (cs.AI, cs.LG, stat.ML, etc.)
- Submission date
- PDF URL

### Phase 2: User Tagging (Manual)
**You**: Browse papers and tag ones you find interesting

```
Papers displayed → You click "Interesting" or custom tags
                → arxiv-sanity-lite learns your preferences
```

**Tag examples**:
- "agents" (for agentic AI papers)
- "insurance" (for insurance/finance)
- "interpretability" (for XAI)
- "document-understanding" (for OCR/parsing)
- "llm-agents" (for LLM-based agents)

### Phase 3: ML-Powered Recommendations (Automated)
**Daily**: System generates personalized recommendations

```
Your tagged papers → TF-IDF feature vectors on abstracts
                   → SVM similarity scoring
                   → Ranked recommendations
                   → Email alert (optional)
```

**Recommendation Logic**:
- Papers with similar abstracts to your likes
- Papers citing papers you tagged
- Papers by authors you follow
- Papers in your topic area published that day

### Phase 4: Email Alerts (Optional)
**Daily morning**: Get an email with top recommendations

```
Subject: arXiv-sanity recommendations for [Date]

Top papers for you:
1. [Title] - Relevance: 92%
2. [Title] - Relevance: 87%
3. [Title] - Relevance: 81%
...

[Click here to view all recommendations]
```

---

## Key Features

### 1. Search Interface
```
🔍 Search by:
   - Keywords ("agent", "insurance", "multimodal")
   - Author names ("Bengio", "LeCun")
   - Subject (cs.LG, cs.AI, q-fin)
   - Date range (past month, year, custom)
   - Sort by: recency, relevance, popularity (arxiv score)
```

### 2. Paper Tagging System
```
When viewing a paper:
   ✅ Click "Interesting" → Paper added to "Interesting" collection
   + Custom tags: Add your own labels ("high-priority", "benchmark", "technique:transformer")
   → System learns your preferences
```

### 3. Personalized Feed
```
Dashboard shows:
   📌 Your tagged papers (curated by you)
   🤖 Recommended papers (ML-suggested based on your interests)
   📅 New papers in your topics (today's submissions)
   🔔 Follow-ups (papers citing your collection)
```

### 4. Batch Operations
```
Multiple selection:
   ☑️ Select papers you want to save
   📥 Export to BibTeX, JSON, CSV
   📧 Email links to yourself
   📎 Add to Zotero/Mendeley
```

### 5. Trending & Statistics
```
Trending papers:
   - Most-viewed today
   - Most-tagged by community
   - Highest arxiv score (votes from other users)

Statistics:
   - Papers per subject this month
   - Your tag cloud (visualize your interests)
   - Comparison to community (are your interests mainstream?)
```

---

## Machine Learning Behind Recommendations

### TF-IDF + SVM Approach
1. **Feature Extraction**: Convert abstract text to TF-IDF vectors
2. **Similarity Scoring**: Compute cosine similarity between paper vectors
3. **SVM Ranking**: Support Vector Machine ranks papers by relevance
4. **Personalization**: Weight scores based on your tagging history

### Why This Works
- **Fast**: TF-IDF is simple and runs instantly
- **Interpretable**: You can see *why* a paper was recommended (similar keywords in abstract)
- **Tunable**: Weights can be adjusted based on feedback
- **No cold-start problem**: Works even for new users tagging papers

### Why Not Deep Learning?
- Overkill for this task (TF-IDF/SVM is nearly as effective)
- TF-IDF is transparent (you can see keyword matches)
- Doesn't require constant retraining
- Lower computational cost (important for free/low-cost hosting)

---

## Self-Hosting Option

The project is open-source and can be self-hosted:

```bash
git clone https://github.com/karpathy/arxiv-sanity-lite.git
cd arxiv-sanity-lite

# Install dependencies
pip install -r requirements.txt

# Initialize database
python fetch_arxiv_papers.py  # Downloads today's papers

# Run local server
python app.py  # Runs on http://localhost:5000
```

**Self-hosting benefits**:
- Privacy (all your tags stay on your server)
- Custom filtering (modify recommendation logic)
- Local arXiv mirror (no network dependency)
- Integration with other tools (API access)

---

## Use for DAC-UW-Agent Knowledge Base

### Continuous Paper Discovery

arxiv-sanity-lite is your **"early warning system"** for relevant papers. Use it to:

1. **Set up tracking** for key topics:
   - Tag papers on: agents, insurance, human-in-the-loop, document understanding, multimodal AI, interpretability
   - Create custom tags for your interest areas

2. **Get daily recommendations** via email
   - Subscribe to email alerts
   - Each morning, review top recommendations
   - Quick decision: "Worth adding to sources?" → Click & save

3. **Review promising papers**
   - Export matches to CSV/BibTeX
   - Batch-download PDFs
   - Quickly skim abstracts to decide inclusion

4. **Feed into ingestion workflow**
   - Papers you decide to ingest → Add to `sources/` folder
   - Follow your CLAUDE.md ingestion workflow (Extract → Synthesize → Update Index)

### Recommended Tags for Your Domain

Create these tags in arxiv-sanity-lite:

```
ai-agents          Papers on agent systems, multi-agent orchestration
insurance-ai       Papers on AI in insurance, actuarial science
document-ai        Papers on document parsing, OCR, information extraction
llm-agents         Papers on LLM-based agents (Claude, GPT agents)
human-ai-collab    Papers on human-in-the-loop, augmented intelligence
interpretability   Papers on XAI, model explainability, auditability
multimodal         Papers on multimodal AI (vision + language)
workflow-orchestration Papers on workflow engines, task scheduling
compliance-ai      Papers on AI governance, regulatory compliance
medical-ai         Papers on medical AI (relevant for health insurance)
```

### Workflow Integration

```
[Daily Routine]
  1. 09:00 AM: Check email alerts from arxiv-sanity
  2. 09:15 AM: Read abstracts of top 10 recommended papers
  3. 09:30 AM: Decide which papers to investigate
  4. 09:45 AM: Download PDFs of selected papers → sources/
  5. [Later]: Ingest per CLAUDE.md workflow

[Weekly Review]
  1. Export all papers tagged "ai-agents" since last week
  2. Skim 10–15 abstracts (30 min)
  3. Select top 3–5 for ingestion
  4. Create wiki entries per CLAUDE.md phases
  5. Update MEMORY.md with key insights
```

---

## Comparison to ResearchPooler

| Feature | arxiv-sanity-lite | ResearchPooler |
|---|---|---|
| **Data source** | arXiv preprints (continuous) | Conference proceedings (static) |
| **Freshness** | Daily updates (real-time) | Periodic (depends on conference schedule) |
| **Setup** | Web app (no local setup needed) | Local Python + PDF parsing |
| **Query method** | Web UI (browser) | Python API (programmatic) |
| **Personalization** | Automatic (ML recommendations) | Manual (write custom queries) |
| **Scale** | 100+ papers/day in ML | Depends on conferences downloaded |
| **Best for** | Staying current with new papers | Deep literature review of specific venues |
| **Hosting** | arxiv-sanity-lite.com (free) or self-host | Local or self-hosted |

---

## Workflow: Using Both Tools Together

**arxiv-sanity-lite** (real-time) + **ResearchPooler** (deep dives):

```
[Initial Setup]
  1. Set up ResearchPooler locally: Download NIPS, ICML, ICLR archives
  2. Set up arxiv-sanity-lite account: Create tags for your interests
  3. Subscribe to daily email alerts

[Daily/Weekly]
  arxiv-sanity-lite: Check recommendations, add to "To Review" list
  
[Monthly Deep Dive]
  ResearchPooler: Query specific topic ("agentic insurance underwriting")
  → Find all relevant papers from past 5 years
  → Compare with arxiv-sanity findings
  → Identify missed papers and key trends

[Ingestion Pipeline]
  Candidates (from both tools) → Review → Accept/Reject → sources/ → CLAUDE.md workflow
```

---

## Limitations

- **Broad recommendations**: System can't distinguish between papers about agents (ML) vs. real estate agents (off-topic)
- **Requires manual tagging**: Have to actively use the system; passive browsing gives no recommendations
- **arXiv only**: Misses papers from venues not on arXiv (some ACM conferences, proprietary research)
- **No full-text search**: Search is title/abstract only; can't find papers by specific dataset or method name

---

## Quick Start (For Your Use Case)

1. **Go to** https://arxiv-sanity-lite.com (or self-host locally)

2. **Browse papers** by category:
   - CS > Machine Learning
   - CS > Artificial Intelligence
   - Finance > General Finance

3. **Create tags** for your interests:
   - Click "Interesting" on papers you like
   - Add custom tags ("insurance", "agents", "document-ai")

4. **Wait 1 day**, then check email for recommendations

5. **Review daily recommendations** (5 min), download promising papers

6. **Add to `sources/`** and ingest per your workflow

---

## Related Tools

- **[ResearchPooler](../sources/2026-04-10_researchpooler.md)** — Complementary tool for conference paper archives
- **Workflow**: [Paper Discovery Workflow](../topics/paper-discovery-workflow.md) — How to use arxiv-sanity-lite + ResearchPooler together

---

## References

- **GitHub**: https://github.com/karpathy/arxiv-sanity-lite
- **Live Instance**: https://arxiv-sanity-lite.com
- **Author**: Andrej Karpathy (Tesla AI, co-founder of OpenAI)
- **Philosophy**: "Efficient paper discovery in the era of information overload"
