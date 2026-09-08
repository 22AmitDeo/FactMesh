# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user is a reviewer or hiring evaluator walking through the Superjoin VIT 2026 intern assignment demo. They open the dashboard to upload PDFs, inspect grounded facts, and show the four required relationship cases without needing a walkthrough.

## Product Purpose

FactMesh is a Fact Knowledge Layer: it extracts structured facts from complex PDF filings, grounds each fact in verified character spans and spatial bounding boxes, and discovers cross-document relationships (corroborations, contradictions, and context-reconciled differences) using incremental vector retrieval and LLM reasoning.

Success on the dashboard: a first-time visitor immediately understands that mechanism and can run the four demonstration cases without help.

## Positioning

Every extracted fact is evidence-grounded (quote substring, character offsets, bbox) and then compared incrementally across documents — not a generic PDF chat UI and not a full knowledge-graph product.

## Operating Context

Local FastAPI app with a static HTML/CSS/JS dashboard. Typical flow: drop PDFs (filings, reports, decks) → wait while pages stream and facts extract → scan the fact mesh → inspect evidence → review corroborates / contradicts / reconciled relationships. Starter datasets and four named demonstration cases live in the repo README.

## Capabilities and Constraints

- PDF-only ingest; page-by-page streaming extraction; incremental relation discovery.
- Dashboard is the REST API presentation layer: Documents, Facts, Relationships, evidence inspector. Existing API calls and behavior must stay.
- Stack is already decided: FastAPI + vanilla HTML/CSS/JS, no CSS frameworks, no JS libraries.
- Do not invent customers, benchmarks, pricing, extra product features, or commercial claims.
- Accessibility standard is undecided.

## Brand Commitments

Name: FactMesh. Subtitle/positioning line in use: Fact Knowledge Layer. Visual world is being replaced in a separate redesign; this file does not record that look.

## Evidence on Hand

Real product copy and flows in `app/static/`. Architecture, highlights, and the four demonstration cases in `README.md`. Starter PDFs under `starter-datasets/`. No testimonials, press, or customer logos — do not fabricate them.

## Product Principles

- Mechanism first: extraction, grounding, and cross-document relation types must be visible as the job, not as afterthought chrome.
- Evidence is the proof: a fact without a path back to quote/span/bbox is incomplete.
- Assignment honesty: demonstrate what the system actually does; do not dress it as a shipped SaaS with invented scale or customers.
- Incremental mesh: new documents add to an existing fact layer; the UI should make that accumulation readable.
