# Competitor Moves 7 and 8

## Move 7 - Transparent model picker and cost meter

Rival tools hide which model answers and meter every call in credits.
ReSearch Flow runs everything on the local Ollama server, so this move
makes that visible instead of asking researchers to trust it.

### Model picker

- `GET /api/v1/models` lists the models actually installed on the local
  Ollama server (`/api/tags`), with size in bytes/MB, parameter size,
  context length, family and capabilities, plus which chat and embedding
  model is active. When Ollama is unreachable it says so honestly and
  returns an empty list.
- `POST /api/v1/models/select` switches the active chat or embedding
  model. The choice is validated against the installed list (unknown
  models and wrong-kind models, e.g. an embedding model as the chat
  model, are rejected with 400) and persisted in a local JSON file,
  `backend/data/model_selection.json` (gitignored machine state, never
  committed). `llm_provider` reads the persisted choice, so switching
  the picker changes the model used by summarize, chat, draft, deep
  review and PRISMA without a restart.
- Frontend: `ModelPicker.jsx` (chat-model dropdown with size/context)
  and `UsagePanel.jsx`, both shown on the home page.

### Cost meter

- Every LLM task (summarize, ask, draft, deep review, prisma) records
  one line in a local JSONL log, `backend/data/usage_log.jsonl`
  (gitignored): task, model, prompt/generated token estimates and wall
  time. Token counts are estimates (about 4 characters per token) and
  the response says so.
- `GET /api/v1/usage` aggregates the log per task and in total, and
  shows the cloud price the same tokens would have cost at the
  published GPT-4o-mini rate: $0.15 per 1M input tokens, $0.60 per 1M
  output tokens (OpenAI pricing page, openai.com/api/pricing, accessed
  2026-11-14). Total spent is always $0.00 because every call runs
  locally.

## Move 8 - Honest drafting

Drafts used to be free-form model output. They are now built from an
extraction table and checked before anyone relies on them.

### Extraction table

`generate_draft(..., papers=[...])` builds one row per source paper
(problem, method, key result, verbatim quote) from the papers supplied
by the caller, or from the single paper being drafted from when no
papers are given. Fields a paper does not supply are filled from its
abstract, never from model memory. The model is instructed to build
every factual claim only from the table and to end each factual
sentence with the citation number of the paper it came from, like [1].

### Unsupported-claim highlighter

After generation, every draft sentence is checked against the source
texts (`check_sentence_support`): token overlap first (threshold 0.30,
the same as citation verification), with the embedding check in
`verify_claim` as fallback for sentences that fail overlap. The
generate response carries `sentence_support` (one flag per sentence:
supported, citations, score, supporting sentence, source paper) and a
`support_summary` (supported / unsupported counts). The frontend
highlights unsupported sentences in red in the draft view and shows
the counts.

### Pre-export check

`POST /api/v1/draft/check` takes the cited papers and:

- checks every DOI against the badges service (OpenAlex
  `is_retracted`). Export is **blocked** when any cited paper is
  retracted (`export_allowed: false`, with the retracted papers named).
- flags possible contradictions: two cited papers sharing topic words
  where one reports a no-effect / negation finding and the other a
  positive effect. These are warnings only, labelled "possible
  contradiction", and never block export.
- warns honestly when a DOI has no OpenAlex record (retraction status
  unknown) instead of pretending it was checked.

The frontend "Check before export" button in the draft view runs this
check and shows the result; the .txt download is refused while the
check says export is blocked.

## Tests

Mocked tests in `backend/src/app/tests/test_api.py`:
`TestModelPickerAndUsage` (9 tests) and `TestHonestDrafting` (8 tests).
Full suite: 156 tests, all passing.
