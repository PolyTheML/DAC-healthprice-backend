# Visual Grounding in Document AI

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md), Lessons 4-6

## Definition

**Visual grounding**: Linking every extracted piece of information back to its source pixels in the original document.

**Example**:
```
Extracted: "Net sales in 2023: $383 billion"
Grounding: "Page 28, Table 3, Row 5, Column 2"
Proof: [Cropped image showing exact table cell]
```

---

## Why It Matters

### For Users (Trust)

Users don't blindly trust LLM outputs. Visual grounding lets them verify:
- "Is this answer correct?"
- "Where did you get this number?"
- "Can I see the source?"

**Behavior**: When users verify a few answers and see they're correct, they trust the system for future queries.

### For Compliance (Audit Trail)

In regulated industries (finance, healthcare, insurance, legal), decisions must be defensible:
- **Auditor asks**: "Where did you get this number?"
- **You show**: "Page 28, table 3, row 5, column 2" + cropped image
- **Auditor verifies**: Can see with own eyes where information came from
- **Liability protected**: Clear documentation of decision basis

### For Developers (Debugging)

When building systems, visual grounding helps identify errors:
- "Why did the system extract the wrong value?"
- Look at the cropped image → immediately obvious (OCR error, layout misunderstanding, etc.)
- **Faster iteration** than debugging with text alone

---

## How Visual Grounding Works

### Step 1: Bounding Box

Every extracted chunk has **bounding box** (rectangle coordinates in original document):

```
bbox = [x1, y1, x2, y2]
Example: [100, 150, 300, 170]  // (left, top, right, bottom) in pixels
```

### Step 2: Image Cropping

Use bbox to crop original PDF/image:

```python
cropped = original_image[y1:y2, x1:x2]
```

### Step 3: Storage & Retrieval

**Local** (Lesson 5):
- Store cropped images in ChromaDB metadata
- Retrieve and display alongside search results

**Cloud** (Lesson 6):
- Generate cropped image on-demand
- Upload to S3
- Return presigned URL to user
- User clicks link → sees cropped image

### Step 4: Annotation (Optional)

For human review, overlay:
- Bounding box (highlight the region)
- Chunk ID (label for reference)
- Extraction result (show what was extracted)
- Confidence score (model confidence)

---

## Technical Requirements

### Data Requirements

Must have:
1. **Bounding box coordinates** for each extracted item
2. **Original document** (PDF or image) to crop from
3. **Chunk ID** for reference

### System Requirements

Must support:
1. **Image cropping** (PIL, OpenCV, PyMuPDF)
2. **Storage** (S3, disk, database)
3. **Display** (web UI, notebook, PDF)

---

## Implementation in Course

### Lesson 4 (Lab: Field Extraction)

When extracting utility bill fields:
```
account_number: "12345"
  ├─ source: chunk_0-a (table cell)
  ├─ page: 0
  ├─ bbox: [50, 100, 200, 120]
  └─ grounding_image: [cropped PNG showing "12345"]
```

### Lesson 5 (Lab: RAG with Grounding)

When user asks "What was Apple's net sales in 2023?":
1. Retrieve relevant chunks
2. For each chunk:
   - Show text
   - Show page number
   - Show bbox
   - Generate & display cropped image (optional)
3. LLM synthesizes answer using retrieved chunks

### Lesson 6 (Lab: AWS Production)

When Strands agent answers question:
1. Agent calls `search_knowledge_base` tool
2. Tool retrieves chunks from Bedrock Knowledge Base
3. Tool checks if chunk is from valid medical_chunks/ folder
4. Tool extracts bbox metadata
5. Tool **generates cropped image** from original PDF (in S3)
6. Tool uploads cropped image to S3 (presigned URL)
7. Agent returns: Answer + Source + Image URL
8. User can click URL → see visual proof

---

## Relevance to DAC-UW

**Insurance underwriting is heavily regulated** → visual grounding is critical.

### Underwriting Decision

**Scenario**: Underwriter reviews application, system recommends "approve with 15% premium loading"

**Questions**:
- Why this premium loading?
- What medical conditions justify it?
- Which documents support this?

**With visual grounding**:
```
Recommendation: Approve with 15% premium loading

Supporting evidence:
1. Hypertension (Stage 2)
   - Source: Medical report, page 3, Table 1 (vital signs)
   - Grounding: [image showing BP 160/100]
   
2. Obesity
   - Source: Medical report, page 1 (vital signs)
   - Grounding: [image showing Height 5'10", Weight 220 lbs, BMI 31.6]

3. Smoker
   - Source: Medical questionnaire, page 2, Question 4
   - Grounding: [image showing "Yes, current smoker, 10 cigs/day"]
```

**Audit trail**: 
- Who reviewed? (underwriter name)
- When? (timestamp)
- What was considered? (three factors above)
- What evidence? (visual proof for each)

### Compliance

**Regulatory audit**: "We found this applicant was rejected. Why?"

**With visual grounding**:
- System shows exactly which extracted fields triggered rejection
- System shows original pixels for each field
- No ambiguity; clear documentation

**Without visual grounding**:
- "System said they were rejected" (but how do we verify?)
- Applicant claims misrepresentation
- Hard to defend in court

---

## Limitations

### What Visual Grounding Doesn't Solve

- ❌ **Domain reasoning**: Grounding shows the numbers; underwriting rules interpret them
- ❌ **Consistency checking**: Grounding proves what was extracted; separate validation checks consistency
- ❌ **Authenticity**: Grounding shows pixels; can't prove document isn't forged (need document verification separately)
- ❌ **Completeness**: Grounding shows what was found; doesn't tell you what's missing

### Image Quality

Cropped images are only as good as original:
- Blurry original → blurry cropped image
- Low-quality scan → hard to read crop
- Handwriting → crop might be hard to read

**Mitigation**: Use confidence scores; flag low-confidence extractions for manual review.

---

## See Also

- [Lesson 4: Agentic Document Extraction](./lesson-4-agentic-document-extraction.md) — Where grounding comes from
- [Lesson 5: RAG for Document Understanding](./lesson-5-rag-for-document-understanding.md) — How grounding is used in RAG
- [Lesson 6: Production Deployment on AWS](./lesson-6-production-aws-deployment.md) — Grounding at scale
- [Entity: Agentic Document Extraction (ADE)](../entities/agentic-document-extraction.md) — Provides grounding
