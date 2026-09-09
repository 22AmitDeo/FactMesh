# FactMesh

An end-to-end Fact Knowledge Layer that extracts structured facts from PDF documents, grounds every fact in verified character spans and spatial bounding boxes, and discovers cross-document relationships — corroborations, contradictions, and context-reconciled differences — using incremental vector retrieval and LLM reasoning.

---

## Video Demo

https://youtu.be/leD2jIQZTmk

---

## Setup and Run Instructions

**Prerequisites:** Python 3.10, 3.11, or 3.12

```bash
git clone <your-repo-url>
cd FactMesh

# Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Description |
| :--- | :--- |
| `GROQ_API_KEY` | Groq API key — enables Llama extraction (free tier available at console.groq.com) |
| `GROQ_MODEL` | Model name, e.g. `llama-3.1-8b-instant` |
| `GEMINI_API_KEY` | Google Gemini API key — used as secondary fallback |

> **No keys required.** If neither key is set, FactMesh automatically activates the offline heuristic extractor. All features — upload, extraction, relationship discovery, and the web UI — remain fully functional.

### Run

```bash
# Windows
py -m uvicorn app.main:app --reload --port 9000

# Linux / macOS
uvicorn app.main:app --reload --port 9000
```

- **Web Dashboard** — http://localhost:9000
- **Swagger API Docs** — http://localhost:9000/docs

### Tests

```bash
py -m pytest tests/ -v
```

Covers: PDF parsing, evidence grounding, embeddings, incremental indexing, and API endpoints.

---

## Approach, Architecture, and Trade-offs

### Architecture

```
[ PDF Upload ]
      │
      ▼
[ PyMuPDF Page Streamer ]          ← page-by-page generator, no full-file RAM load
      │
      ▼
[ Bounded Concurrency Pool ]       ← asyncio.Semaphore(3) caps concurrent LLM calls
      │
      ├─────────────────────────────────────────┐
      ▼                                         ▼
[ LLM Extraction Engine ]          [ Substring Verification Guard ]
  Groq Llama (Primary)               validates exact quote substring
  Gemini Flash (Fallback)            flags hallucinations, computes
  Heuristic Engine (Offline)         char span + [x0,y0,x1,y1] bbox
      │                                         │
      └─────────────────────────────────────────┘
                        │
                        ▼
              [ SQLite Database ]               ← dynamic extra: JSON schema
                        │
                        ▼
           [ Sentence-Transformers ]            ← all-MiniLM-L6-v2 embeddings
                        │
                        ▼
           [ Incremental ANN Index ]            ← top-k cosine retrieval, k=5, threshold ≥ 0.50
                        │
                        ▼
           [ LLM Relationship Judge ]           ← Corroborates / Contradicts / Reconciled / Unrelated
                        │
                        ▼
         [ REST API + Web Dashboard ]           ← Evidence Inspector, Cross-Document Mesh
```

### Key Decisions and Trade-offs

**1. Page-by-page streaming instead of full-document ingestion**

Loading a 100-page PDF into a single LLM prompt hits context limits and spikes RAM. PyMuPDF streams pages as a generator — one page at a time — so memory usage stays flat regardless of document size. An `asyncio.Semaphore(3)` caps concurrent LLM calls to avoid rate-limit errors (HTTP 429) while keeping throughput high.

**2. Substring verification guard against hallucinations**

LLMs sometimes return quoted excerpts that do not appear verbatim in the source text. Every extracted quote is checked as a strict substring of the raw page text before the fact is persisted. If the check fails, the fact is flagged with a reduced confidence score and stored separately for human review rather than silently discarded or trusted.

**3. Dynamic schema via a JSON extra column**

Financial documents contain wildly different fact types — some have time scopes, some have currencies, some have geographies. Rather than adding columns for every new attribute, the core schema fixes `subject`, `predicate`, `value`, `page`, `char_start`, `char_end`, and `bbox`, while an `extra: JSON` column captures everything else. New fact attributes appear automatically without any migrations.

**4. Incremental vector retrieval instead of O(N²) pairwise comparison**

Comparing every fact against every other fact is quadratic — with 500 facts across three documents that is 250,000 LLM calls. When a new document is ingested, its facts are embedded with `sentence-transformers/all-MiniLM-L6-v2` and queried against the existing index for the top-5 nearest candidates (cosine similarity ≥ 0.50, cross-document only). Only those candidates go to the LLM relationship judge. Cost scales as O(M × k) — linear in new facts, not total facts.

**5. Three-tier LLM stack**

Groq Llama is the primary engine for fast structured extraction. Gemini Flash is the fallback if Groq fails or rate-limits. A deterministic heuristic extractor runs offline when no API keys are configured. This means the system can be evaluated without any paid credentials.

---

## The Four Required Cases

The following cases were produced by uploading the three Delhivery starter documents:
`01-delhivery-prospectus-2022-excerpt.pdf`, `02-delhivery-annual-report-fy24-excerpt.pdf`, and `03-delhivery-q4-fy24-earnings-presentation.pdf`.

---

### Case 1 — Corroborated Fact

Two documents assert the same operational metric using different phrasing and units.

| | Fact |
| :--- | :--- |
| **Document A** | Delhivery Annual Report FY24 |
| **Source quote** | *"In FY24, Delhivery express parcel volume crossed 740 million shipments."* |
| **Document B** | Q4 FY24 Earnings Presentation |
| **Source quote** | *"Our core parcel delivery business handled over 740M packages during the 2023-24 financial year."* |

**System reasoning:** Both facts share the same subject (Delhivery express parcel volume), the same time scope (FY24 / 2023-24), and the same value (740 million). The surface phrasing differs — "shipments" vs "packages", "crossed" vs "handled over" — but the semantic content is identical. Classified as **Corroborates**.

---

### Case 2 — Genuine Contradiction

Two documents report conflicting values for the same entity at the same point in time.

| | Fact |
| :--- | :--- |
| **Document A** | Delhivery Annual Report FY24 |
| **Source quote** | *"Permanent full-time headcount stood at 31,200 as of March 31, 2024."* |
| **Document B** | Delhivery Q4 FY24 Earnings Presentation |
| **Source quote** | *"Total full-time workforce was reported as 27,450 at fiscal year-end 2024."* |

**System reasoning:** Both facts refer to the same entity (Delhivery full-time headcount), the same date (March 31, 2024 / fiscal year-end 2024), and the same predicate (headcount). The values are irreconcilable — 31,200 vs 27,450 — with no qualifying scope difference that explains the gap. Classified as **Contradicts**. Flagged for human audit.

---

### Case 3 — Apparent Contradiction Reconciled by Context

Two revenue figures look contradictory but are explained by different time scopes.

| | Fact |
| :--- | :--- |
| **Document A** | Q4 FY24 Earnings Presentation |
| **Source quote** | *"Q4 FY24 Revenue from Operations stood at INR 2,076 Crore."* |
| **Document B** | Delhivery Annual Report FY24 |
| **Source quote** | *"Full year FY24 revenue from operations grew to INR 8,142 Crores."* |

**System reasoning:** The values differ — ₹2,076 Cr vs ₹8,142 Cr — which would be a contradiction if both referred to the same period. The dynamic schema captured `time_scope: Q4 FY24` from Document A and `time_scope: Full Year FY24` from Document B. The LLM judge identifies this scope difference and explains that ₹2,076 Cr is a single-quarter figure while ₹8,142 Cr is the annual total. Classified as **Reconciled** with `difference_type: time_scope`.

---

### Case 4 — Extraction Failure and How It Was Handled

**What failed:** Several pages in the Delhivery Prospectus contain multi-level financial tables where row headers span multiple columns and body rows use relative pronouns — e.g. *"Express Parcel | Part Truckload | Supply Chain. It increased by 14% over the prior period."* The LLM extracted `subject: "It"` and returned a quote that did not appear verbatim in the source text.

**How the system handled it:** The substring verification guard checked the returned quote against the raw page text. The match failed. The fact was saved with `is_hallucinated_quote: true` and `confidence: 0.30` rather than being silently trusted or discarded. It appears in the Facts table with a **Hallucination Flagged** badge and is excluded from relationship discovery.

**What would fix it:** Two improvements would address the root cause. First, a layout-aware table parser (`pdfplumber` or `LayoutLMv3`) would correctly associate each data cell with its full header path, eliminating the ambiguous pronoun problem at the source. Second, a coreference resolution pass (`fastcoref`) before extraction would resolve "It" to its antecedent before the LLM ever sees the sentence.

---

## Limitations and Next Steps

**Table hierarchy** — PyMuPDF flattens multi-level table headers into plain text. Cells lose their column and row context, which causes the LLM to produce vague subjects. A layout-aware parser would fix this.

**Coreference resolution** — Pronouns and anaphoric references ("It", "The division", "This segment") without explicit antecedents in the same sentence require manual review. A `fastcoref` pass before extraction would resolve these automatically.

**Vector storage** — The current ANN index is in-memory NumPy with SQLite persistence. This works for hundreds of documents but would not scale to tens of thousands. The right replacement is `pgvector` on PostgreSQL or a dedicated vector database like Milvus.

**Relationship recall** — The cosine similarity threshold of 0.50 filters out some genuine relationships where the phrasing is too different for the embedding model to catch. A hybrid retrieval approach — dense vectors plus sparse BM25 — would improve recall without increasing LLM call volume.

**Single-page context** — Facts are extracted one page at a time. A fact that spans a page break (e.g. a sentence that starts on page 42 and ends on page 43) will be missed or truncated. A sliding window over adjacent pages would handle this.

---

## Stack

| Layer | Technology |
| :--- | :--- |
| Backend | FastAPI, SQLite, PyMuPDF |
| LLM | Groq (Llama), Google Gemini, offline heuristic fallback |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Frontend | Vanilla HTML / CSS / JS |

---

## AI Tools Used

- **Groq API (Llama)** — primary LLM for fact extraction and relationship classification at runtime.
- **HuggingFace Sentence-Transformers** — dense fact embeddings for candidate retrieval.
