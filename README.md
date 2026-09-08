# FactMesh — Fact Knowledge Layer

> **Superjoin VIT 2026 — Engineering Intern Assignment**  
> An end-to-end Fact Knowledge Layer that extracts structured facts from complex PDF filings, grounds every fact in verified character spans and spatial bounding boxes, and discovers cross-document relationships (Corroborations, Contradictions, and Context-Reconciled differences) using incremental vector retrieval and LLM reasoning.

---

## 🎥 Video Demo

- **Demo Video Link:** `[Insert 3-Minute Loom / YouTube Video Link Here]`
- *A complete scene-by-scene demonstration walkthrough is documented in the video script notes.*

---

## 🌟 Key Highlights & Brownie Points Addressed

| Feature | Implementation Mechanism | Brownie Point Addressed |
| :--- | :--- | :--- |
| **Large PDFs (100+ Pages)** | Page-by-page streaming generator via PyMuPDF (`fitz.open()`) with bounded concurrent worker tasks governed by `asyncio.Semaphore(3)`. Avoids loading large PDFs into RAM at once. | **Large PDFs** |
| **Many PDFs / Scale** | Facts are embedded (`all-MiniLM-L6-v2`) and indexed in an incremental ANN vector store. Pairwise comparisons are restricted strictly to top-$k$ nearest candidates ($k=5$, cosine $\ge 0.50$), avoiding $O(N^2)$ brute-force explosion. | **Many PDFs / Scale** |
| **Dynamic Open Schema** | SQLite `extra: JSON` column combined with Pydantic open models. Facts require `(subject, predicate, value)` while open attributes (`time_scope`, `unit`, `entity_type`, `currency`, `geography`) are captured dynamically without migrations. | **Dynamic Schema** |
| **Incremental Ingestion** | When document $M$ is uploaded, only its newly extracted facts are compared against pre-existing indexed facts. Pre-existing relations are never recomputed from scratch. | **Incremental Ingestion** |
| **Hallucination Guard** | Substring verification checks every quoted evidence excerpt against the raw source page text. Inexact or hallucinated quotes are flagged with reduced confidence and audited. | **Failure Handling** |

---

## 🏛️ System Architecture

```
                                [ PDF Upload / CLI ]
                                          │
                                          ▼
                               [ PyMuPDF Page Streamer ]
                               (Page-by-page stream generator)
                                          │
                                          ▼
                         [ Bounded Concurrency Worker Pool ]
                         (asyncio.Semaphore caps LLM calls)
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
       [ LLM Extraction Engine ]                     [ Substring Verification Guard ]
        Groq Llama 3.3 70B (Primary)                  Validates exact quote substring
        Gemini 2.0 Flash (Fallback)                   Flags ungrounded hallucinations
        Deterministic Heuristic (Offline)             Computes char span & [x0,y0,x1,y1] bbox
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          │
                                          ▼
                                [ SQLite Database Store ]
                                  Document & Fact Models
                                (Dynamic `extra: JSON` schema)
                                          │
                                          ▼
                             [ Sentence-Transformers ]
                            Vectorize Subject+Pred+Value
                                          │
                                          ▼
                             [ Incremental ANN Index ]
                          Retrieve Top-k Candidate Facts
                             (Exclude same-document facts)
                                          │
                                          ▼
                             [ LLM Relationship Judge ]
                           Corroborates / Contradicts /
                           Reconciled-by-Context / Unrelated
                                          │
                                          ▼
                              [ REST API & Web Dashboard ]
                             Grounded Evidence Inspector &
                               Cross-Document Mesh Graph
```

---

## 🧪 The Four Required Demonstration Cases

| Case | Scenario | Documents & Source Quotes | System Reasoning |
| :--- | :--- | :--- | :--- |
| **1. Corroborated Fact** | Same metric phrased with different units | **Doc 1 (Annual Report):** *"In FY24, Delhivery express parcel volume crossed 740 million shipments."*<br>**Doc 2 (Earnings Deck):** *"Over 740M packages handled in full-year FY24."* | Evaluates "740 million shipments" and "740M packages" as synonymous representations for the same period (FY24), classifying the relationship as **Corroborating**. |
| **2. Direct Contradiction** | Conflicting values for the identical entity & timestamp | **Doc 1 (Annual Report):** *"Permanent full-time headcount stood at 31,200 as of March 31, 2024."*<br>**Doc 2 (Investor Memo):** *"Total full-time workforce was reported as 27,450 on March 31, 2024."* | Flags an irreconcilable discrepancy (31,200 vs 27,450) sharing identical scope and timestamp as a **Contradiction** requiring human audit. |
| **3. Reconciled by Context** | Apparent conflict explained by differing time scope | **Doc 1 (Q4 Earnings):** *"Q4 FY24 Revenue stood at INR 2,076 Cr."*<br>**Doc 2 (Annual Report):** *"Full year FY24 revenue grew to INR 8,142 Crores."* | Reconciles ₹2,076 Cr vs ₹8,142 Cr by extracting `time_scope` (`Q4 FY24` vs `Full Year FY24`), classifying as **Reconciled by Context**. |
| **4. Handled Failure Case** | Anaphoric pronoun & complex table fragment | **Source Text:** *"Express Parcel \| Part Truckload \| Supply Chain. It increased by 14% over prior period."*<br>**Naive LLM Output:** Subject `"It"`, hallucinated quote. | Substring Verification Guard catches the non-verbatim quote, flags the fact as an ungrounded hallucination, and reduces confidence to 0.30. |

---

## 🚀 Setup and Run Instructions

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 2. Clone and Install Dependencies
```bash
# Clone the repository
git clone <your-repo-url>
cd FactMesh

# (Optional) Create a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Set your free-tier API keys if available:
- `GROQ_API_KEY`: For ultra-fast Llama 3.3 70B extraction & relation reasoning.
- `GEMINI_API_KEY`: For Gemini 2.0 Flash secondary fallback.

> **Zero-Key Evaluation Note:** If no API keys are provided in `.env`, FactMesh automatically engages its intelligent heuristic fallback engine so that all tests, the web UI, and the demo seed script run completely out of the box without requiring external credentials!

### 4. Run the 4 Demo Cases Seed Script
To automatically generate curated seed filings, execute end-to-end ingestion, and print the verification report:
```bash
python demo/seed_demo.py
```

### 5. Launch the Web Application
```bash
uvicorn app.main:app --reload --port 8000
```
Open your browser and navigate to:
- **Interactive Web Dashboard:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Run Automated Test Suite
```bash
python -m pytest tests/ -v
```
*(All 21 unit and integration tests will execute covering parsing, grounding, embeddings, incremental indexing, and API endpoints).*

---

## 🛠️ Approach, Architecture & Engineering Trade-Offs

### 1. Multi-Tier LLM Service Architecture
- **Decision:** Primary engine uses Groq (`llama-3.3-70b-versatile`) for sub-second inference and high-fidelity structured JSON reasoning; Google Gemini 2.0 Flash is configured as a fallback; an offline semantic heuristic acts as a fail-safe.
- **Trade-Off:** Provides production-grade speed and intelligence while ensuring the submission repository can be evaluated offline or in air-gapped CI environments without paid dependencies.

### 2. Bounded Streaming vs Full-File Ingestion
- **Decision:** Rather than feeding a 100-page filing to an LLM context window, PyMuPDF streams pages sequentially, and an `asyncio.Semaphore(3)` bounds concurrent extraction requests.
- **Trade-Off:** Prevents rate limiting (HTTP 429), controls peak memory consumption, and guarantees precise page-level grounding.

### 3. Strict Evidence Grounding & Hallucination Guard
- **Decision:** Every extracted quote is subjected to a substring verification check against the raw page text before database persistence. Spatial bounding box coordinates (`[x0, y0, x1, y1]`) and normalized coordinates are recorded.
- **Trade-Off:** Rejects or flags hallucinated spans, giving analysts verifiable audit trails for every extracted metric.

### 4. Incremental Candidate Retrieval vs $O(N^2)$ Pairwise Comparisons
- **Decision:** Newly ingested facts are embedded with `sentence-transformers/all-MiniLM-L6-v2`. Candidates are filtered using vector dot-product similarity (top-$k$, threshold $\ge 0.50$) across existing documents only.
- **Trade-Off:** Reduces relationship reasoning complexity from $O(N^2)$ to $O(M \cdot k)$, enabling the knowledge base to scale linearly with new documents.

---

## 🚧 Limitations & Next Steps

1. **Dense Financial Table Hierarchy**:
   - *Current Limitation:* Standard text extraction flattens multi-level table headers.
   - *Next Step:* Integrate a layout-aware table parser (e.g. `pdfplumber` or `LayoutLMv3`) to trace table cells directly to their hierarchical row and column headers.
2. **Coreference Resolution**:
   - *Current Limitation:* Sentences containing relative pronouns ("It", "The division", "This segment") without explicit antecedents require human inspection.
   - *Next Step:* Add a dedicated neural coreference resolution pass (e.g. `fastcoref`) to resolve anaphoric pronouns before fact extraction.
3. **Enterprise Vector Storage**:
   - *Current Limitation:* Uses an in-memory normalized NumPy index with SQLite persistence for simplicity.
   - *Next Step:* Swap to PostgreSQL with `pgvector` or Milvus for horizontal clustering across millions of corporate disclosures.

---

## 🤖 AI Tools Used
- **Antigravity AI Pair Programming Agent:** Used for project scaffolding, incremental test-driven development, and architectural design.
- **Groq API (Llama 3.3 70B):** Used for extraction prompt development and cross-document reasoning.
- **HuggingFace Sentence-Transformers:** Used for dense fact embedding and cosine similarity ranking.
