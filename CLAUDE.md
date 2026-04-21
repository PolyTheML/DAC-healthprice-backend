# Knowledge Base Schema

**Version**: 2.0 (adapted from Karpathy's autoresearch pattern)

This document defines the structure, conventions, and workflows for maintaining this persistent wiki-based knowledge base. It is intentionally minimal and opinionated—like autoresearch, we use a three-layer architecture with clear ownership, single modification points per operation, and measurable success criteria.

## Three-Layer Architecture

### Layer 1: Raw Sources (`/sources`) — *Immutable*
- **Owner**: User (you)
- **Modification rule**: Never modified by Claude
- **Contents**: All source documents (articles, PDFs, images, notes, transcripts)
- **Naming**: `YYYY-MM-DD_descriptive-title.ext` (date prefix for chronological scanning)
- **Purpose**: Source of truth; everything in the wiki traces back to these sources

### Layer 2: Wiki (`/wiki`) — *Mutable by Claude*
- **Owner**: Claude (LLM maintainer)
- **Modification rule**: Claude only; generated from sources
- **Contents**: Synthesized entity pages, concept pages, summaries, synthesis
- **Cross-reference rule**: All pages linked with relative paths `[text](../wiki/page.md)`
- **Purpose**: Compiled knowledge; always fresh and up-to-date with sources
- **Core structure**:
  - `index.md` — Content catalog (curated by user input)
  - `log.md` — Append-only operational log
  - `synthesis.md` — High-level thesis (updated when themes shift)
  - `topics/` — Concept/topic pages (one idea per page)
  - `entities/` — Entity pages (people, orgs, products, etc.)
  - `sources/` — Summary pages for each ingested source

### Layer 3: Schema (This File) — *Governance*
- **Owner**: User + Claude (co-evolved)
- **Purpose**: Instructions for operations, conventions, role definitions
- **Update rule**: When we discover patterns that work, we add them here
- **Analogy**: Like autoresearch's `program.md` — humans edit this to shape Claude's behavior

## Naming Conventions

- **Filenames**: `lowercase-with-hyphens.md` (kebab-case)
- **Internal links**: `[Link Text](../wiki/page-name.md)` (relative paths, never absolute)
- **Dates**: Always ISO format `YYYY-MM-DD`
- **Headers**: Start new pages with H1 (`#`), use H2+ (`##`, `###`) for sections
- **Citations**: Inline source references where facts stated: `per [source-name](../wiki/sources/source-name.md)`
- **Metadata**: Track creation date and last update date on entity/concept pages

## Ingestion Workflow

**Time budget**: ~10-15 minutes per source  
**Files modified**: `wiki/sources/*`, `wiki/entities/*`, `wiki/topics/*`, `wiki/index.md`, `wiki/log.md`  
**Files untouched**: Everything in `sources/`, `CLAUDE.md`, `README.md`

### Phases

**Phase 1: Extract** (Claude, ~3 min)
1. Read entire source thoroughly
2. Identify key facts, claims, entities, and concepts
3. Note contradictions or surprising claims
4. List new entities and topics not yet in wiki

**Phase 2: User Guidance** (~2 min)
5. Present summary: "Here's what I extracted. Should I emphasize X over Y?"
6. User provides direction: focus areas, de-emphasis, special connections to existing knowledge

**Phase 3: Synthesize** (Claude, ~5-10 min)
7. Create source summary page in `wiki/sources/YYYY-MM-DD_source-name.md`
8. Create or update entity pages in `wiki/entities/` (one per new entity)
9. Create or update topic pages in `wiki/topics/` (incorporating new information)
10. Check: Each new fact is cited back to the source page
11. Check: Each new page is linked from relevant existing pages (cross-references)
12. Flag any contradictions: "Source X claims Y, but wiki/sources/Z claims ¬Y"

**Phase 4: Bookkeeping** (Claude, ~1 min)
13. Update `wiki/index.md` with new pages
14. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | Source Title` with change summary
15. Report to user: "Added N pages, revised M pages, found C contradictions"

### Quality Checks
- ✓ All source summaries have metadata: `Source: [filename]`, `Ingested: [date]`
- ✓ All entity/topic pages cite sources inline
- ✓ No page is orphaned (all have at least 2 inbound links)

## Query Workflow

**Time budget**: ~5-10 minutes per question  
**Files modified**: `wiki/index.md`, `wiki/log.md`, optionally new pages in `wiki/`  
**Files untouched**: Everything in `sources/`, `CLAUDE.md`, existing source summaries

### Phases

**Phase 1: Search** (Claude, ~2 min)
1. Scan `wiki/index.md` to find relevant pages
2. Read all cross-linked pages gathering context

**Phase 2: Synthesize** (Claude, ~3-5 min)
3. Construct answer using wiki pages as source material
4. Cite sources inline: "According to [page-name](../wiki/page-name.md), ..."
5. Flag missing information: "Not covered in current sources"

**Phase 3: User Dialog** (~1-2 min)
6. Present answer and ask: "Does this answer your question? Want me to file this as a wiki page?"
7. If user says yes → Phase 4. If no → discuss follow-ups.

**Phase 4: Optional Filing** (Claude, ~2-3 min)
8. If answer is substantial/reusable, create new page: `wiki/queries/YYYY-MM-DD_question-slug.md`
9. Add to `wiki/index.md` under appropriate category
10. Link from related pages

**Phase 5: Bookkeeping** (Claude, ~1 min)
11. Append to `wiki/log.md`: `## [YYYY-MM-DD] query | Question summary`

### Quality Checks
- ✓ Every factual claim is cited
- ✓ Answer acknowledges what's not in the knowledge base
- ✓ If filed as a page, it has cross-links to related pages

## Lint/Maintenance Workflow

**Time budget**: ~20-30 minutes per lint pass  
**Trigger**: Every 5-10 sources ingested, or when user requests  
**Files modified**: `wiki/` pages (fixes), `wiki/log.md` (report)  
**Files untouched**: Everything in `sources/`, `CLAUDE.md`, README.md

### Phases

**Phase 1: Scan** (Claude, ~5 min)
1. Read all pages in `wiki/` looking for issues
2. Build three lists:
   - **Contradictions**: Claims that conflict across pages (fact X vs ¬X)
   - **Orphans**: Pages with zero inbound links
   - **Staleness**: Claims superseded by newer sources (date-based)

**Phase 2: Measure Health Metrics** (Claude, ~5 min)

Report these quantitative metrics:
- **Contradiction count** — # of conflicting claim pairs found
- **Orphan count** — # of pages with no inbound links
- **Link density** — Average # of links per page (target: 3-5 links/page)
- **Citation coverage** — % of factual claims with source citations (target: >95%)
- **Staleness index** — # of pages without major updates in >3 months (sorted by age)

**Phase 3: Identify Gaps** (Claude, ~5 min)
3. Missing entity/concept pages: things mentioned that lack their own page
4. Cross-reference gaps: pages that should link but don't (e.g., Topic A mentions Concept B, but no link)
5. Source gaps: questions the wiki can't answer; suggested web searches or ingestions

**Phase 4: Report & Recommendations** (Claude, ~3-5 min)
6. Generate report with:
   - Metrics summary (contradiction count, orphan count, link density, etc.)
   - Specific issues found (with page names and line references)
   - Recommendations: "Merge pages X and Y (contradictory)", "Delete orphaned page Z", "Add 3 missing cross-references"
7. Append to `wiki/log.md`: `## [YYYY-MM-DD] lint | Summary of findings`

**Phase 5: Optional Fixes** (User decision, ~varies)
8. User selects which recommendations to act on
9. Claude implements them (merge, delete, add links, rewrite)
10. User reviews, approves, or requests changes

### Health Target Metrics
- Contradictions: **0** (flag all)
- Orphans: **0** (pages should have ≥2 inbound links)
- Link density: **3-5 per page** (fewer than 3 = isolated; more than 5 = over-linked)
- Citation coverage: **>95%** (every fact needs a source)
- Max staleness: **3 months** (pages should be reviewed quarterly)

## Log Format

Every operation appends one entry to `wiki/log.md` for auditability:

```markdown
## [YYYY-MM-DD HH:MM] operation | Description

Summary of what happened.
- Specific change 1
- Specific change 2

Metrics: X new pages, Y revised pages, Z contradictions found (if applicable)
```

**Parse with**: `grep "^## \[" wiki/log.md` to see all operations  
**Read recent**: `tail -20 wiki/log.md` to see latest activity

## Operational Conventions

### Immutability Rules
- **sources/** — Never modified by Claude after user adds file
- **CLAUDE.md** — Only user + Claude modify (discussion first)
- **README.md, QUICKSTART.md** — Only user modifies; Claude reads for reference
- Everything in **wiki/** — Claude owns; user reads and guides via feedback

### Link Rules
- Always relative: `[Link](../wiki/page.md)` not `[Link](./wiki/page.md)` or absolute URLs
- When linking to entities: `[Entity Name](../entities/entity-name.md)`
- When citing sources: inline as `per [source-name](../wiki/sources/source-name.md)`

### Header Structure (consistent across all pages)
```markdown
# Page Title (H1, appears once per page)

## Section One (H2, major sections)

Content...

### Subsection (H3, subdivide as needed)
```

### Metadata Requirements
Every page should include near the top:
```markdown
**Created**: YYYY-MM-DD  
**Last updated**: YYYY-MM-DD  
**Source**: [if applicable, link to source page]
```

### Citation Standard
Every factual claim should cite its source:
- Option A (inline): "X happened per [source](path/to/source.md)."
- Option B (footer): Content... [^1] → [^1]: See [source](path/to/source.md)

## Roles & Responsibilities

### You (User/Source Curator)
- **Decide inputs**: What goes in `sources/`? When to ingest? When to lint?
- **Provide guidance**: "Emphasize X over Y", "This contradicts Z, investigate"
- **Ask questions**: Drive exploration; the wiki should answer your questions
- **Review quality**: Check lint reports, approve/reject recommendations
- **Update schema**: When patterns emerge, propose updates to CLAUDE.md

### Claude (LLM/Wiki Maintainer)
- **Execute workflows**: Ingest sources, answer queries, run lints (per the phases above)
- **Maintain coherence**: Ensure all claims are sourced; all entities linked properly
- **Preserve immutability**: Never touch `sources/` or user files
- **Produce auditable logs**: Every operation recorded in log.md
- **Flag issues**: Contradictions, gaps, stale pages; let user decide fixes
- **Suggest, not decide**: Lint recommendations are advisory; user approves changes

## Autoresearch Connection

This schema is inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch):
- **Three-layer architecture**: sources (immutable data) | wiki (mutable synthesis) | schema (instructions)
- **Single modification point per workflow**: Like `train.py`, each operation modifies specific files only
- **Measurable outcomes**: Health metrics replace vague "quality checks"
- **Time budgets**: Workflows have explicit duration targets
- **Human-in-the-loop**: Humans edit the instructions (schema); Claude executes and reports

## Quick Start

1. **Add your first source**: Drop a PDF, article, or notes file into `sources/`
2. **Request ingestion**: Tell Claude, "Ingest [filename]"
3. **Review & discuss**: Look at the summary; give feedback on emphasis
4. **Ask questions**: "What are the main themes?" "Tell me about [topic]"
5. **Maintain**: Every 5-10 sources, request "Lint the wiki"

## When to Lint

**Recommended lint cadence**:
- After every 5-10 sources ingested
- If you suspect contradictions
- Before major decisions (to ensure knowledge is current)
- Quarterly, minimum (keep staleness < 3 months)
