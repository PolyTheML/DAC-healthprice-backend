# Paper Discovery Workflow: Populating the Knowledge Base

**Tag**: Meta / Knowledge Base Maintenance  
**Type**: Operational Workflow  
**Created**: 2026-04-10  
**Last Updated**: 2026-04-10

---

## Overview

The **Paper Discovery Workflow** is a systematic approach to find academic papers related to your agentic underwriting system, then ingest them into your knowledge base per your CLAUDE.md ingestion workflow.

**Goal**: Transform research discovery from a *passive* activity ("Did I miss any important papers?") to an *active, automated* system ("Here are the 5 most relevant papers published this week").

**Tools Used**:
- [arxiv-sanity-lite](../sources/2026-04-10_arxiv-sanity-lite.md) — Real-time arXiv monitoring (daily updates)
- [ResearchPooler](../sources/2026-04-10_researchpooler.md) — Deep conference archive analysis (one-time or quarterly)

---

## Three-Tier System

### Tier 0: Fully Automated Discovery (Research Automation System) ⭐ **NEW**
**Frequency**: Daily (automated)  
**Effort**: 0 min/day (hands-off)  
**Best for**: Continuous, unattended paper ingestion without human effort

1. **Setup** (5 minutes, one-time): Configure `research_automation/config.py` with keywords + thresholds
2. **Start** (one command): `python background_runner.py --mode background`
3. **Automation runs** (9 AM daily, configurable):
   - Query arXiv API for papers matching your interests
   - Score each by relevance (0.0–1.0)
   - Auto-ingest top-N papers to `wiki/sources/` as markdown
   - Deduplicate (never re-ingests same paper)
   - Log all results for monitoring

**Advantages**:
- ✅ Truly hands-off (0 effort/day)
- ✅ Never misses papers (runs every day)
- ✅ Deduplicates automatically
- ✅ Runs 24/7 on laptop, no setup required

**Limitations**:
- ⚠️ Titles/abstracts only (no full-text analysis)
- ⚠️ arXiv-only (ResearchPooler integration coming)
- ⚠️ Scores papers automatically (but you can adjust keywords/thresholds)

**Recommended for**: Always-on, maintenance-free operation + Tier 1/2 for occasional deep dives

**See**: [Research Automation System](../sources/2026-04-10_research-automation-system.md) — Complete setup guide + architecture

---

### Tier 1: Real-Time Discovery (arxiv-sanity-lite)
**Frequency**: Daily (manual)  
**Effort**: 5–10 min/day  
**Best for**: Interactive browsing + learning author preferences

1. **Email arrives** (daily morning): Top 10 recommendations from arxiv-sanity-lite
2. **Quick skim** (5 min): Read abstracts of top 5–10 papers
3. **Triage decision**: 
   - 🟢 Highly relevant → Add to "Daily Candidates" list
   - 🟡 Potentially relevant → Add to "Monthly Review" list
   - 🔴 Not relevant → Skip
4. **Batch download** (optional): End of week, download all candidates as PDFs
5. **Weekly review** (1–2 hours): Deeper read of top candidates

### Tier 2: Deep Dives (ResearchPooler)
**Frequency**: Monthly or quarterly  
**Effort**: 2–4 hours per dive  
**Best for**: Comprehensive topic analysis

1. **Topic selection**: Choose a key area to explore (e.g., "human-in-the-loop AI")
2. **Run queries**: Use ResearchPooler to find all relevant papers from conferences (NIPS, ICML, ICLR, AAAI) from past 3–5 years
3. **Export results**: Get list of 50–200 candidate papers
4. **Skim abstracts**: Filter down to ~20 most promising
5. **Read & decide**: Deep-read 10–20 papers, select top 3–5 for ingestion
6. **Ingest**: Per CLAUDE.md workflow (Extract → Synthesize → Update Index)

---

## Setup Instructions

### Phase 1: arxiv-sanity-lite Configuration (20 minutes)

1. **Go to** https://arxiv-sanity-lite.com
   - Create an account (free)
   - Set up email notifications (optional but recommended)

2. **Create tags** for your research areas:
   ```
   Tags to create:
   - ai-agents              (multi-agent systems, agent orchestration)
   - insurance-ai           (AI in insurance, actuarial science)
   - human-in-the-loop      (augmented intelligence, human oversight)
   - document-ai            (document parsing, OCR, information extraction)
   - llm-agents             (LLM-based agents, Claude agents)
   - interpretability       (XAI, model explainability, auditability)
   - multimodal-ai          (vision + language, document understanding)
   - workflow-orchestration (workflow engines, task scheduling, LangGraph)
   - compliance-ai          (AI governance, regulatory compliance)
   - medical-ai             (medical/health AI, biomedical NLP)
   - credit-scoring         (credit risk, credit assessment, lending)
   - loan-origination       (LOS, underwriting, lending platforms)
   ```

3. **Browse initial papers**:
   - Go to CS > Machine Learning category
   - Search for "agent" or "insurance"
   - Click "Interesting" on papers that match your interests
   - Add custom tags (e.g., tag a paper with both "ai-agents" and "interpretability")

4. **Subscribe to email alerts**:
   - Settings → Email Notifications
   - Choose: "Daily summary" or "Weekly digest"
   - Select your preferred categories (Machine Learning, AI, NLP)

5. **First recommendation email**: Arrives next morning
   - Check inbox, review top papers
   - Begin tagging papers you like

### Phase 2: ResearchPooler Setup (30 minutes)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/karpathy/researchpooler.git
   cd researchpooler
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Download conference archives** (this takes time; best overnight):
   ```bash
   # NeurIPS (largest ML conference)
   python scripts/nips_fetch.py
   
   # ICML (machine learning)
   python scripts/icml_fetch.py
   
   # ICLR (deep learning)
   python scripts/iclr_fetch.py
   
   # AAAI (AI)
   python scripts/aaai_fetch.py
   
   # Optional: ACL (NLP), KDD (data mining)
   python scripts/acl_fetch.py
   python scripts/kdd_fetch.py
   ```

4. **Create a Python script** for your queries (`my_queries.py`):
   ```python
   # my_queries.py
   from researchpooler import load_papers
   
   papers = load_papers()  # Load all downloaded papers
   
   # Query 1: Agentic AI papers
   agentic_papers = [p for p in papers 
                     if any(word in p['title'].lower() 
                            for word in ['agent', 'multi-agent', 'agentic'])]
   
   # Query 2: Insurance/underwriting
   insurance_papers = [p for p in papers 
                       if any(word in p['abstract'].lower() 
                              for word in ['insurance', 'underwriting', 'actuarial'])]
   
   # Query 3: Human-in-the-loop
   hitl_papers = [p for p in papers 
                  if 'human' in p['abstract'].lower() 
                  and 'loop' in p['abstract'].lower()]
   
   # Query 4: Interpretability/XAI
   xai_papers = [p for p in papers 
                 if any(word in p['abstract'].lower() 
                        for word in ['interpret', 'explainable', 'xai', 'explainability'])]
   
   # Combine and deduplicate
   candidates = set()
   for p in agentic_papers + insurance_papers + hitl_papers + xai_papers:
       candidates.add(p['id'])
   
   # Export to CSV
   import csv
   with open('paper_candidates.csv', 'w') as f:
       writer = csv.writer(f)
       writer.writerow(['Title', 'Authors', 'Year', 'Venue', 'Abstract'])
       for paper_id in sorted(candidates):
           p = papers[paper_id]
           writer.writerow([p['title'], p['authors'], p['year'], p['venue'], p['abstract'][:200]])
   
   print(f"Exported {len(candidates)} candidates to paper_candidates.csv")
   ```

5. **Run your queries**:
   ```bash
   python my_queries.py
   # Output: paper_candidates.csv (open in Excel/Google Sheets)
   ```

---

## Daily/Weekly Workflow

### Daily (5 min)
```
09:00 AM: Email arrives with arxiv-sanity recommendations
09:05 AM: Read top 5 abstracts
09:10 AM: Decide: "Worth deeper look?" → Save to Candidates list
```

### Weekly (1–2 hours)
```
Friday afternoon:
  1. Review all papers tagged "interesting" this week (15 min)
  2. Read abstracts of candidates (30 min)
  3. Deep-read 3–5 most promising (60 min)
  4. Download PDFs of top 2–3 (5 min)
  5. Add to sources/ folder (5 min)
  
Next week:
  Begin CLAUDE.md ingestion workflow (Extract → Synthesize → Update Index)
```

### Monthly (2–4 hours)
```
First Sunday of month:
  1. Select topic to deep-dive (e.g., "workflow orchestration")
  2. Run ResearchPooler queries on that topic (5 min)
  3. Export candidates list (5 min)
  4. Skim 50+ abstracts, narrow to 20 (30 min)
  5. Deep-read 10–20 papers (2–3 hours)
  6. Select top 3–5 for ingestion (15 min)
  
Next weeks:
  Ingest per CLAUDE.md workflow
```

---

## Decision Tree: Should I Ingest This Paper?

```
Found a paper from arxiv-sanity or ResearchPooler

    ↓ [Read Abstract]
    
    ├─ Not related to agentic underwriting?
    │  └─ ❌ Skip
    │
    ├─ Related but already in wiki (similar concepts)?
    │  └─ 🔍 Check existing sources
    │     ├─ Already cited? → ❌ Skip
    │     └─ Adds new perspective? → ✅ Ingest
    │
    ├─ Related + novel perspective?
    │  ├─ Directly applicable (e.g., "LangGraph multi-agent patterns")?
    │  │  └─ ✅ High Priority: Ingest this week
    │  │
    │  ├─ Adjacent field (e.g., "Finance AI" but not insurance)?
    │  │  └─ 🟡 Medium Priority: Ingest this month
    │  │
    │  └─ Tangentially relevant (e.g., "General ML" with agent discussion)?
    │     └─ 🟢 Low Priority: Ingest if time permits
    │
    └─ Read full paper to decide?
       ├─ Time investment: 30–60 min per paper
       ├─ Verdict: Include if it teaches you something new
       └─ Add to "Deep Reading" queue
```

---

## Integration with CLAUDE.md Ingestion Workflow

Once you've selected a paper via discovery tools, follow your standard ingestion workflow:

### Phase 1: Extract (Claude, 3 min)
1. Read paper thoroughly
2. Identify key facts, claims, concepts
3. Note contradictions or surprising claims
4. List new entities and topics

### Phase 2: User Guidance (You, 2 min)
5. Present summary: "Here's what I extracted. Should I emphasize X over Y?"
6. Provide direction: focus areas, de-emphasis, connections

### Phase 3: Synthesize (Claude, 5–10 min)
7. Create source summary in `wiki/sources/YYYY-MM-DD_paper-title.md`
8. Create/update entity pages in `wiki/entities/`
9. Create/update topic pages in `wiki/topics/`
10. Check: Each new fact is cited
11. Check: Each new page is linked

### Phase 4: Bookkeeping (Claude, 1 min)
13. Update `wiki/index.md` with new pages
14. Append to `wiki/log.md` with ingestion record
15. Report: "Added N pages, revised M pages"

---

## Example: Ingesting a Paper on Agent Orchestration

### Step 1: Discovery
- arxiv-sanity emails you: "New paper on multi-agent systems"
- Title: "Scalable Multi-Agent Reinforcement Learning via Graph-Based Communication"
- Abstract mentions: agents, LangGraph, state management, orchestration
- Decision: ✅ HIGH PRIORITY (directly relevant to Phase 3 work)

### Step 2: Download & Add to sources/
- Download PDF from arXiv
- Save to `sources/2026-04-10_scalable-multi-agent-rl.pdf`

### Step 3: Request Ingestion
- Message me: "Ingest 2026-04-10_scalable-multi-agent-rl.pdf"
- I read and extract key insights

### Step 4: Your Guidance
- You review my summary and ask: "Emphasize the graph-based communication pattern and how it compares to our LangGraph approach"

### Step 5: Synthesis
- I create: `wiki/sources/2026-04-10_scalable-multi-agent-rl.md`
- I update: `wiki/topics/agent-orchestration.md` (add new section on graph-based communication)
- I link from: `wiki/topics/agentic-workflows-orchestration.md`
- I cross-reference: Related pages on LangGraph, state management

### Step 6: Update Index & Log
- Index updated with new source
- Log records: "2026-04-10 ingest | Scalable Multi-Agent RL — Added 1 source page, revised 2 topics, connection found to LangGraph state management"

---

## Metrics & Success

### Track What You're Finding

**Weekly**:
- How many arxiv-sanity recommendations? (target: 10+)
- How many "Interesting"? (target: 3–5)
- How many added to "Candidates"? (target: 1–2)

**Monthly**:
- How many papers ingested? (target: 3–5)
- How many new wiki topics created? (target: 1–2)
- How many existing topics updated? (target: 3–5)

**Quarterly**:
- Growth in sources folder? (target: 5–10 new sources)
- Growth in wiki? (target: 2–3 new topics)
- Repeated citations? (source A cites source B = validation of knowledge relevance)

### Health Check

Ask yourself:
- 🟢 Are papers from 2024–2026? (recent)
- 🟢 Are they from top venues (NeurIPS, ICML, ICLR)? (credible)
- 🟢 Do they relate to your thesis (agents, insurance, governance)? (relevant)
- 🟢 Do they reference each other? (coherent knowledge area)

---

## Limitations & Caveats

1. **Both tools miss some papers**:
   - ResearchPooler only covers venues you download
   - arxiv-sanity misses non-arXiv papers (some ACM conferences, proprietary research)
   - **Mitigation**: Use both tools + manual Google Scholar searches for specific topics

2. **arXiv has more breadth than depth**:
   - Many papers on arXiv are preprints (some never published)
   - Quality varies; not all preprints are rigorous
   - **Mitigation**: Prioritize published conference papers; use publication venue as signal

3. **Topic drift**:
   - "Agent" could mean RL agent, LLM agent, real estate agent, sales agent
   - Recommend tagging/filtering by multiple keywords to reduce false positives
   - **Mitigation**: Use compound searches (e.g., "agent" + "orchestration", not just "agent")

4. **Time investment**:
   - Reading 50 abstracts to find 5 good papers = 80% of time in filtering
   - **Mitigation**: Trust the recommendation algorithm; read top 10, not all 100

---

## See Also

- [Research Automation System](../sources/2026-04-10_research-automation-system.md) — Fully automated discovery + ingestion (hands-off)
- [arxiv-sanity-lite](../sources/2026-04-10_arxiv-sanity-lite.md) — Interactive manual discovery tool
- [ResearchPooler](../sources/2026-04-10_researchpooler.md) — Deep conference archive analysis
- **CLAUDE.md**: Standard ingestion workflow (Extract → Synthesize → Bookkeeping)
- [Knowledge Base Schema](../../CLAUDE.md) — Three-layer architecture (sources → wiki → schema)

---

## Quick Reference

### arxiv-sanity-lite URL
https://arxiv-sanity-lite.com

### ResearchPooler GitHub
https://github.com/karpathy/researchpooler

### Recommended Time Budget
- **Daily**: 5 min (email review)
- **Weekly**: 1–2 hours (deep read + download)
- **Monthly**: 2–4 hours (quarterly deep-dive + ingestion)
- **Total**: ~3–5 hours/week for research discovery + ingestion
