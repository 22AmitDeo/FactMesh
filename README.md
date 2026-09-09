# FactMesh

An end-to-end Fact Knowledge Layer that extracts structured facts from PDF documents, grounds every fact in verified character spans and spatial bounding boxes, and discovers cross-document relationships — corroborations, contradictions, and context-reconciled differences — using incremental vector retrieval and LLM reasoning.

Video Link: https://youtu.be/leD2jIQZTmk
---

## Architecture

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

---

## Key Design Decisions

| Concern | Approach |
| :--- | :--- |
| Large PDFs (100+ pages) | PyMuPDF page-by-page streaming with `asyncio.Semaphore(3)` — avoids loading full files into RAM |
| Scale across many PDFs | Incremental ANN index — new facts compared only against existing index, not recomputed pairwise |
| Dynamic fact schema | SQLite `extra: JSON` column + Pydantic open models — no migrations needed for new attributes |
| Hallucination detection | Substring verification against raw page text before persistence — flagged facts get reduced confidence |
| Offline / zero-key use | Deterministic heuristic extractor activates automatically when no API keys are configured |

---

## Setup

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

---

## Configuration

Copy `.env.example` to `.env` and set your API keys:

```bash
cp .env.example .env
```

| Variable | Description |
| :--- | :--- |
| `GROQ_API_KEY` | Groq API key — enables Llama extraction (free tier available) |
| `GROQ_MODEL` | Model name, e.g. `llama-3.1-8b-instant` |
| `GEMINI_API_KEY` | Google Gemini API key — used as secondary fallback |

> If no keys are set, FactMesh automatically falls back to the offline heuristic engine. All features remain functional.

---

## Running

```bash
# Windows (use py launcher)
py -m uvicorn app.main:app --reload --port 9000

# Linux / macOS
uvicorn app.main:app --reload --port 9000
```

Open in your browser:

- **Web Dashboard** — http://localhost:9000
- **Swagger API Docs** — http://localhost:9000/docs

---

## Tests

```bash
py -m pytest tests/ -v
```

Covers: PDF parsing, evidence grounding, embeddings, incremental indexing, and API endpoints.

---

## Relationship Types

| Type | Description |
| :--- | :--- |
| **Corroborates** | Two facts assert the same claim, possibly with different phrasing or units |
| **Contradicts** | Two facts assert conflicting values for the same entity and time scope |
| **Reconciled** | Apparent conflict explained by differing context (e.g. Q4 vs full-year revenue) |

---

## Limitations

- **Table hierarchy** — multi-level table headers are flattened during text extraction. A layout-aware parser (`pdfplumber`, `LayoutLMv3`) would improve accuracy.
- **Coreference** — pronouns and anaphoric references ("It", "The division") without explicit antecedents require manual review. A `fastcoref` pass would resolve these before extraction.
- **Vector storage** — uses an in-memory NumPy index with SQLite persistence. For production scale, replace with `pgvector` or Milvus.

---

## Stack

- **Backend** — FastAPI, SQLite, PyMuPDF
- **LLM** — Groq (Llama), Google Gemini, offline heuristic fallback
- **Embeddings** — `sentence-transformers/all-MiniLM-L6-v2`
- **Frontend** — Vanilla HTML / CSS / JS
