# ResearchPooler: Automated Research Publication Discovery

**Source**: https://github.com/karpathy/researchpooler  
**Type**: Tool / Literature Review Automation  
**Author**: Andrej Karpathy  
**Ingested**: 2026-04-10  
**Status**: Maintained project (flexible, extensible framework)

---

## Executive Summary

**ResearchPooler** (repool) is a Python-based automation tool that solves a core problem: "Literature review is much harder than it should be." It systematically downloads, parses, and indexes academic papers from various venues, making them searchable and analyzable via simple Python queries.

Instead of manually browsing conference proceedings or arXiv, ResearchPooler lets researchers:
- Download entire conference archives (NIPS, ICML, ICLR, etc.)
- Parse PDFs into structured metadata (title, authors, venue, abstract, full text)
- Query papers programmatically (find papers on topic X, similar to paper Y, using dataset Z)
- Automatically batch-open PDFs matching search criteria

---

## Four-Stage Pipeline

### Stage 1: Data Gathering
**Goal**: Download all papers from a venue

```
python scripts/nips_fetch.py  # Downloads NIPS proceedings
python scripts/icml_fetch.py  # Downloads ICML proceedings
# (Extensible: contribute parsers for other conferences)
```

**Outputs**: Raw PDFs organized by year/conference

**Applicable Venues**:
- NeurIPS / NIPS (premier AI conference)
- ICML (machine learning)
- ICLR (learning representations)
- AAAI (artificial intelligence)
- IJCAI (joint AI)
- ACL (computational linguistics)
- SIGMOD (databases)
- VLDB (databases)
- KDD (knowledge discovery & data mining)

### Stage 2: Data Enrichment
**Goal**: Parse PDFs into structured format

```python
# Extracts title, authors, venue, abstract, full text, references
papers = parse_pdfs(raw_pdfs)
# Stores as pickled Python dictionaries for quick access
```

**Metadata Extracted**:
- Title
- Authors (with affiliations if available)
- Venue (conference/journal/year)
- Abstract
- Full PDF text (for searching)
- References (inbound/outbound citations)
- Publication date

### Stage 3: Analysis & Indexing
**Goal**: Make papers queryable

```python
# Build indices for:
- Full-text search
- Title/abstract matching
- Author search
- Citation network
- Similarity metrics (TF-IDF, embeddings)
```

**Enables**:
- Find papers on topic "agentic AI" (keyword search)
- Find papers similar to a given paper (similarity search)
- Find papers citing a specific work
- Find papers by author or affiliation
- Find papers using a specific dataset (e.g., "ImageNet", "Penn Treebank")

### Stage 4: User Interface & Querying
**Goal**: Make results accessible

```python
# Simple Python API for querying
matching_papers = [p for p in papers if 'agent' in p['title'] and p['year'] >= 2024]
for paper in matching_papers:
    webbrowser.open(paper['pdf_url'])  # Batch-open PDFs
```

**Can be extended to**:
- Web dashboard (Flask/FastAPI)
- Email alerts ("New papers on X published today")
- Slack/Discord notifications
- Integration with reference managers (Zotero, Mendeley)

---

## Key Use Cases

### 1. Rapid Literature Review
**Goal**: Understand what's been published on a topic

```python
# Find all papers on "multimodal learning" from 2023–2026
papers = [p for p in database 
          if ('multimodal' in p['abstract'] or 'multimodal' in p['title'])
          and 2023 <= p['year'] <= 2026]

print(f"Found {len(papers)} papers")
for p in papers[:10]:  # Show top 10
    print(f"  {p['title']} ({p['year']})")
```

### 2. Find Similar Work
**Goal**: Understand prior art related to your research

```python
# Given a paper ID, find similar papers
reference_paper = get_paper_by_id("arxiv:2312.06234")
similar = find_similar_papers(reference_paper, k=20)

# Batch-open all similar papers
for paper in similar:
    webbrowser.open(paper['pdf_url'])
```

### 3. Dataset-Specific Research
**Goal**: Find all papers benchmarking on a dataset

```python
# Find papers that report results on ImageNet
papers = [p for p in database if 'ImageNet' in p['full_text']]

# Find papers that use specific model architecture
papers = [p for p in database if 'transformer' in p['abstract'].lower()]
```

### 4. Citation Network Analysis
**Goal**: Understand research lineage

```python
# Find all papers citing a seminal work
cited_by = get_papers_citing("attention-is-all-you-need")

# Find all papers cited by a specific paper
cites = get_papers_cited_by("arxiv:2404.00000")
```

### 5. Continuous Monitoring
**Goal**: Stay updated on emerging topics (with custom automation)

```python
# Check daily for new papers on topic
schedule.every().day.at("09:00").do(
    find_and_email_new_papers,
    keywords=['agentic', 'AI', 'insurance'],
    email='user@example.com'
)
```

---

## Technology Stack

- **Language**: Python 3.8+
- **PDF Parsing**: PyPDF2, pdfplumber, or custom parsers
- **Data Storage**: Pickle files (simple) or SQLite/PostgreSQL (scalable)
- **Search**: Full-text search via regex or elasticsearch
- **Similarity**: TF-IDF vectors, word embeddings (Word2Vec, FastText), or neural embeddings
- **UI (optional)**: Flask, FastAPI, Streamlit

---

## Extensibility

### Add New Conference/Journal
Create a parser for any venue:

```python
# scripts/conference_fetch.py (new)
def parse_acl_proceedings():
    """Download and parse ACL conference papers"""
    urls = [...]  # ACL paper URLs
    for url in urls:
        pdf = download(url)
        metadata = extract_metadata(pdf)
        papers.append(metadata)
    return papers
```

### Enhance Analysis
Add custom analysis functions:

```python
def find_papers_with_code():
    """Find papers that mention code availability"""
    papers = [p for p in database 
              if 'github.com' in p['full_text'] 
              or 'code available' in p.get('abstract', '')]
    return papers

def timeline_analysis(topic):
    """Show publication trend over time"""
    papers = find_papers(topic)
    by_year = {}
    for p in papers:
        by_year.setdefault(p['year'], []).append(p)
    return sorted(by_year.items())
```

---

## Limitations

- **Manual setup**: Venue parsers must be written per conference (no universal PDF reader)
- **Metadata quality**: Some conferences have incomplete metadata; full-text search less reliable
- **No automatic tagging**: Unlike arxiv-sanity, doesn't learn user preferences
- **Batch operation**: Designed for programmatic scripting, not interactive exploration

---

## Comparison to arxiv-sanity-lite

| Feature | ResearchPooler | arxiv-sanity-lite |
|---|---|---|
| **Data source** | Conference proceedings (NIPS, ICML, etc.) | arXiv preprints (continuous) |
| **Setup** | Download conference PDFs + parse locally | Poll arXiv API, host web app |
| **Query method** | Python API (list comprehensions) | Web UI (search, tag, recommend) |
| **Personalization** | Manual (write custom queries) | Automatic (ML-based recommendations) |
| **Freshness** | Static (conference archives) | Real-time (daily arXiv updates) |
| **Best for** | Deep literature reviews, specific conferences | Staying current with new papers |
| **Hosting** | Local or self-hosted | Web app (can self-host) |

---

## Use for DAC-UW-Agent Knowledge Base

### Populating `sources/` Folder

You can use ResearchPooler to **automatically discover papers** related to your agentic underwriting system:

1. **Set up queries** for key topics:
   ```python
   # Papers on agentic AI
   agentic_papers = [p for p in papers if 'agent' in p['title'].lower()]
   
   # Papers on insurance/actuarial
   insurance_papers = [p for p in papers if 'insurance' in p['abstract'].lower()]
   
   # Papers on human-in-the-loop AI
   hitl_papers = [p for p in papers if 'human' in p['abstract'] and 'loop' in p['abstract']]
   
   # Papers on interpretability/explainability
   xai_papers = [p for p in papers if 'interpret' in p['abstract'] or 'explainable' in p['abstract']]
   ```

2. **Export matches** to a "To Review" list:
   ```python
   candidates = agentic_papers + insurance_papers + hitl_papers + xai_papers
   export_to_csv(candidates, 'papers_to_review.csv')
   ```

3. **Manually review** promising papers in your PDF reader
4. **Add** selected papers to `sources/` and ingest them per your CLAUDE.md workflow

### Recommended Conferences to Download
For agentic underwriting, focus on:
- **NeurIPS / ICML / ICLR**: Core ML conferences (agent architectures, RL, interpretability)
- **AAAI / IJCAI**: AI (agents, multi-agent systems)
- **ACL**: NLP (document understanding, information extraction)
- **KDD**: Data mining & insurance/finance applications
- **IJCAI Finance**: Financial AI (if available)

---

## Quick Start (For Your Use Case)

1. **Clone the repo**:
   ```bash
   git clone https://github.com/karpathy/researchpooler.git
   cd researchpooler
   ```

2. **Download NIPS + ICML papers** (largest AI conferences):
   ```bash
   python scripts/nips_fetch.py
   python scripts/icml_fetch.py
   ```

3. **Run discovery queries** (see above)

4. **Batch-open promising papers**, review, and add to `sources/`

5. **Ingest via CLAUDE.md workflow** (Extract → Synthesize → Update Index)

---

## Related Tools

- **[arxiv-sanity-lite](../sources/2026-04-10_arxiv-sanity-lite.md)** — Complementary tool for real-time arXiv monitoring
- **Workflow**: [Paper Discovery Workflow](../topics/paper-discovery-workflow.md) — How to use ResearchPooler + arxiv-sanity together

---

## References

- **GitHub**: https://github.com/karpathy/researchpooler
- **Author**: Andrej Karpathy (Tesla AI, co-founder of OpenAI)
- **Philosophy**: Solving "literature review is much harder than it should be"
