# Competitor moves 5 and 6

## Move 5 - Citation graph + gap finder

`POST /api/v1/gap-finder/graph` with `{"doi": "..."}` or
`{"topic": "..."}` (plus optional `max_nodes`, default 60, max 200).
One response carries:

- `graph`: nodes + edges (citing / cited-by) from free OpenAlex and
  Semantic Scholar data, built on the existing citation network code.
- `timeline`: papers by year with paper count, total and average
  citations, and the top-cited paper.
- `under_cited_clusters`: recent years (last 3) with at least 3
  papers, listing the papers below that year's median citation
  count. Deterministic, no LLM.
- `unanswered_questions`: the local Ollama model reads the collected
  abstracts and lists up to 4 questions they do not answer, each tied
  to the papers checked (title + DOI). When the model is unavailable
  the response says so and returns deterministic fallback questions.

Two things the live run caught and fixed:

- OpenAlex often has no abstract for a work, and its search flattens
  a missing abstract to the literal string "N/A". The gap finder
  treats "N/A" as no abstract and enriches missing abstracts from
  Semantic Scholar (single lookup for a seed DOI, one batch call for
  a topic). Papers still without a real abstract (50+ chars) are
  dropped from the question step instead of being "read".
- Deep Review's paper normalizer dropped `paperId`, which made the
  topic-mode graph empty. It now preserves `paperId` / `id`.

Frontend: `/citation-graph` page (graph rendered as SVG, timeline
table, gap-finder panels). Rate limited with the other LLM endpoints
(10/min per IP).

Live verified 2026-11-14: DOI 10.1038/nature12373 gave 19 nodes,
18 edges, 4 LLM questions in 150.7s. Topic "sleep and memory
consolidation" gave 60 nodes, 62 edges, 4 LLM questions in 155.6s.
Topic "large language models" gave 60 nodes, 55 edges and 2
under-cited clusters (2025: 6 papers, median 596; 2024: 14 papers,
median 802) in 193.1s.

## Move 6 - Cross-project private knowledge graph

All state lives on this machine in `backend/data/library/<user>.json`
(papers, notes, entities, topics, last alert check). Nothing is
uploaded anywhere. `user_id` selects the library; the frontend passes
the signed-in user's id, or "local".

- `POST /api/v1/library/index` - index saved papers/notes, extract
  entities per paper with the local LLM (deterministic keyword
  fallback). Dedupes by DOI, merges notes onto existing papers.
- `POST /api/v1/library/sync-saved` - index the user's Supabase
  saved articles (paper ids resolved through OpenAlex for abstracts).
- `GET /api/v1/library/papers` - list the stored library.
- `GET /api/v1/library/graph` - paper and entity nodes; edges for
  paper-mentions-entity and entity co-occurrence. Entities shared by
  2+ papers link papers across projects.
- `POST /api/v1/library/ask` - cross-paper RAG over the user's own
  library: local FAISS (nomic-embed-text) retrieval, local LLM
  synthesis with cited sources, keyword + extractive fallback when
  Ollama is down.
- `POST /api/v1/library/zotero/import` - read-only import from the
  free Zotero API (needs `ZOTERO_API_KEY` and `ZOTERO_USER_ID` in
  `backend/.env`; without them it answers `not_configured`).
- `GET /api/v1/library/zotero/export?format=bibtex|ris` - export the
  library to Zotero-compatible BibTeX / RIS.
- `POST /api/v1/library/alerts/check` and `GET /api/v1/library/alerts`
  - locally computed new-paper alerts: for each saved topic, check
  free OpenAlex for papers published since the last check. No
  external alert service. Note: the OpenAlex request must NOT sort by
  publication date on their side (a date sort ignores the search
  term); the backend uses the default relevance sort and sorts by
  date locally.

Entity extraction note: the first prompt listed example categories
(methods, diseases, datasets...), which the 3B model echoed back as
entities. The prompt now asks only for words that appear in the text,
and a generic-term filter drops leftovers.

Frontend: `/my-library` page (index saved papers, knowledge graph
summary with shared entities, cross-paper ask, Zotero import/export,
alerts list).

Live verified 2026-11-14: indexed 3 real test papers in 32.9s
(24 entities); graph 3 papers, 18 entities, 4 shared
(consolidation, memory, replay, Sleep), 88 edges; cross-paper ask
answered with FAISS retrieval and LLM citations in 39.1s; alerts for
"sleep and memory" returned 10 on-topic papers since 2026-10-15;
BibTeX and RIS export verified; Zotero import answered
`not_configured` (no key in `.env`, import itself covered by mocked
tests).
