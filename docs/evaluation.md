# ReSearch Flow evaluation

Date: 2026-11-12
Model: qwen2.5:3b via local Ollama (no paid APIs)
Hardware: CPU-only, no GPU; 4 CPUs, 7.7 GB RAM; Ollama served on 127.0.0.1:11435
Backend: FastAPI from this repo, run on 127.0.0.1:8001 with
`OLLAMA_BASE_URL=http://127.0.0.1:11435 OLLAMA_CHAT_MODEL=qwen2.5:3b`
Method: every question below was run once against the live backend and timed
with wall-clock measurement. No numbers are invented. Verdicts were judged
against the source paper's abstract or full text.

## Setup notes

- The Ollama binary was missing at the start of this run (lost in a VM restart).
  Ollama 0.40.16 was reinstalled from the GitHub release tarball and served
  manually on port 11435. Both models were already present in ~/.ollama and
  did not need re-pulling: qwen2.5:3b (1.9 GB) and nomic-embed-text (274 MB).
  A warm-up call answered "OK" in 26.3 s (24 s of that was model load).
- Backend startup warnings (not fatal, did not affect this run): Supabase
  credentials not configured, so database features were disabled; Neo4j was
  unreachable on localhost:7687, so the citation mesh used its OpenAlex fallback.
- Search endpoints were checked live first: Crossref 2.8 s, Europe PMC 1.5 s,
  PubMed 2.3 s, DOAJ 1.0 s, arXiv 1.2 s (all HTTP 200, real papers returned).

## Papers used

- P1: "Attention Is All You Need", Vaswani et al., 2017, arXiv 1706.03762 (source: arXiv)
- P2: "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
  Devlin et al., 2019, arXiv 1810.04805 (source: arXiv)
- P3: "Application of transformer attention mechanism-based multimodal deep learning model
  in the diagnosis of papillary thyroid carcinoma", Xu et al., BMC Medical Imaging 2026,
  DOI 10.1186/s12880-026-02530-w, PMID 42374243, PMCID PMC13576103 (source: Europe PMC)
- P4: "MTF-Net: a brain tumor segmentation network with multi-scale transformer and
  feature fusion enhancement", Frontiers in Medicine 2026,
  DOI 10.3389/fmed.2026.1934161, PMID 43005398 (source: PubMed)
- P5: "Over-Sampling Effect in Pre-Training for Bidirectional Encoder Representations
  from Transformers (BERT) to Localize Medical BERT and Enhance Biomedical BERT (Preprint)",
  2022, DOI 10.2196/preprints.40992 (source: Crossref)

## Results table

| # | Type | Endpoint | Paper | Time | Verdict |
|---|------|----------|-------|------|---------|
| S1 | Summarize | POST /api/v1/arxiv/summarize | P1 Attention | 614.3 s | Partially correct |
| S2 | Summarize | POST /api/v1/arxiv/summarize | P2 BERT | 642.0 s | Correct |
| S3 | Summarize | POST /api/v1/crossref/summarize | P5 Over-Sampling BERT | 85.1 s | Correct |
| S4 | Summarize | POST /api/v1/europe-pmc/summarize | P3 PTC ultrasound | 108.6 s | Correct |
| S5 | Summarize | POST /api/v1/pubmed/summarize | P4 MTF-Net | 87.7 s | Correct |
| R1 | RAG ask | POST /api/v1/arxiv/ask | P1 Attention | 237.8 s | Correct |
| R2 | RAG ask | POST /api/v1/arxiv/ask | P1 Attention | 140.9 s | Correct |
| R3 | RAG ask | POST /api/v1/arxiv/ask | P2 BERT | 225.8 s | Correct |
| R4 | RAG ask | POST /api/v1/europe-pmc/ask | P3 PTC ultrasound | 67.6 s | Correct |
| R5 | RAG ask | POST /api/v1/pubmed/ask | P4 MTF-Net | 65.6 s | Correct |

Totals: 9 correct, 1 partially correct, 0 wrong, 0 weak. All 10 calls returned HTTP 200.
Total LLM call time: 2275.4 s (about 38 minutes).

## Per-question details

### S1 - Summarize P1 (Attention), full PDF, 614.3 s, partially correct

Prompt: summarize the paper (arxiv_id 1706.03762, full PDF extracted, 39,511 chars).
Excerpt: structured summary (problem_statement, methodology, key_findings,
conclusion) correctly describing the Transformer as attention-only, stacked
self-attention plus feed-forward layers, and reporting 28.4 BLEU on WMT 2014
English-to-German and 3.5 days of training on 8 GPUs.
Issue: the English-to-French BLEU is given as 41.8 in the problem statement
but as 41.0 in key_findings. The paper's abstract claims 41.8 while its
results table lists 41.0 for the big model, so the summary is internally
inconsistent on this number. Everything else checked was accurate.

### S2 - Summarize P2 (BERT), full PDF, 642.0 s, correct

Prompt: summarize the paper (arxiv_id 1810.04805, full PDF extracted, 64,131 chars).
Excerpt: correctly identifies BERT as deep bidirectional pre-training with MLM
and NSP, fine-tuning with one output layer, and reports GLUE 80.5%,
MultiNLI 86.7%, SQuAD v1.1 F1 93.2 and v2.0 F1 83.1. All numbers match the paper.

### S3 - Summarize P5 (Over-Sampling BERT), abstract fallback, 85.1 s, correct

Prompt: summarize the paper (Crossref, abstract only, 2,945 chars; no PDF was
available, so the endpoint used its abstract fallback and flagged it).
Excerpt: correctly describes over-sampling domain corpora for balanced
pre-training, the three experiments (English biomedical BERT, Japanese medical
BERT, enhanced biomedical BERT), and the BLUE benchmark gain of 0.3 points.

### S4 - Summarize P3 (PTC ultrasound), abstract fallback, 108.6 s, correct

Prompt: summarize the paper (Europe PMC, pdf_url supplied but PDF extraction
failed, so the endpoint used its abstract fallback and flagged it; 1,929 chars).
Excerpt: correctly reports the 491-patient two-center study, comparison of 34
deep learning architectures, the proposed Efficientnetv2scbamTrans model,
and AUCs 0.702 (DenseNet201 external), 0.782 (unimodal baseline), 0.811 (with
clinical features), 0.751 (radiomics fusion), 0.985/0.986 (proposed model).

### S5 - Summarize P4 (MTF-Net), abstract fallback, 87.7 s, correct

Prompt: summarize the paper (PubMed, abstract only, 1,861 chars; the PubMed
page is not a PDF, so the endpoint used its abstract fallback and flagged it).
Excerpt: correctly names MSFormer, CEBAM, CFIM and the BCE + Dice hybrid loss,
and reports BraTS2019 Dice 0.926/0.921/0.896 and BraTS2021 Dice 0.918/0.923/0.901.

### R1 - Ask P1: what is the Transformer and how does it differ from RNN/CNN models? 237.8 s, correct

Answer excerpt: "The Transformer architecture is based entirely on attention
mechanisms, specifically self-attention, which allows it to model dependencies
between input and output sequences without the need for recurrence or
convolution." It correctly contrasts sequential RNN processing, fixed-window
CNNs, and the Transformer's parallelizable stacked self-attention layers, and
notes the 12-hour base-model training claim from the paper.

### R2 - Ask P1: BLEU score and training time, 140.9 s, correct

Answer in full: "The Transformer (big) model achieved a BLEU score of 28.4 on
the WMT 2014 English-to-German translation task. Training took 3.5 days on
8 P100 GPUs." Both facts are exactly right.

### R3 - Ask P2: what two unsupervised tasks pre-trained BERT? 225.8 s, correct

Answer in full: "Two unsupervised tasks were used to pre-train BERT: Masked
Language Model (MLM) and Next Sentence Prediction (NSP)." Exactly right.

### R4 - Ask P3: objective, proposed model, patient count, 67.6 s, correct

Answer: objective was a Transformer-based multimodal deep learning model to
improve ultrasound diagnosis of papillary thyroid carcinoma and benign nodules;
proposed model was the Efficientnetv2scbamTrans fusion model; 491 thyroid
nodule patients from two centers. All three facts match the abstract. (The
endpoint response does not report whether the PDF or the abstract was used as
context; the answer is fully consistent with the abstract.)

### R5 - Ask P4: what problem does MTF-Net address, and what are its main modules? 65.6 s, correct

Answer: insufficient multimodal information fusion and inadequate long-range
feature extraction in brain tumor segmentation; modules MSFormer (multi-scale
deep convolution with spatially-aware MLP, layers 2-4 of the encoder), CEBAM
(dual-layer sparse attention with channel enhancement, last encoder layer),
and CFIM (cross-modal feature interaction in the encoder-decoder bridge).
All match the abstract.

## Overall summary

- Answer quality is good: 9 of 10 correct, 1 partially correct, none wrong.
  The 3B local model answers factual questions about these papers accurately,
  including exact numbers (BLEU 28.4, 3.5 days on 8 P100 GPUs, MLM + NSP,
  491 patients, BraTS Dice scores) when the relevant text is in context.
- Latency is the main problem. Full-PDF summarization took 614-642 s (over
  10 minutes per paper) on this CPU-only machine, and full-PDF RAG questions
  took 141-238 s. Abstract-based calls were far faster at 66-109 s, but still
  slow for interactive use. Total time for the 10 calls was about 38 minutes.
  A user waiting on a summary would likely time out or give up; this setup is
  usable for offline/batch work but not for interactive chat.
- The abstract fallback works and is honest: S3, S4 and S5 all flagged
  `fallback: true` when no PDF could be extracted, and still produced correct
  summaries from the abstract. Note S4's Europe PMC PDF URL
  (europepmc.org/articles/PMC13576103?pdf=render) failed to extract even though
  the article is open access; PDF extraction for that host is worth investigating.

  Follow-up (2026-11-12): root cause found. The europepmc.org website blocks
  automated requests with a Cloudflare challenge (HTTP 403, "Just a moment..."),
  so the `?pdf=render` link can never be downloaded directly. The same full
  text is served without bot protection by the Europe PMC REST API as JATS XML
  (`/rest/{PMCID}/fullTextXML`). `pdf_service.get_pdf_text_from_url` now fetches
  that XML first for europepmc.org article URLs and converts the `<body>` to
  plain text, falling back to the normal PDF download if the XML is unavailable.
  Verified live on the S4 paper: extract returned HTTP 200 with 54,556 chars of
  real full text, and summarize returned HTTP 200 in 336.4 s with
  `fallback: false` and 54,556 chars of context (the summary itself was only
  partly usable: key findings and limitations were accurate, but
  problem_statement and methodology came back as "Unable to extract...", so the
  full-text summarization quality still needs work). Unit tests are now 28/28.

  Follow-up (2026-11-12): the summarization quality issue is fixed. Three
  stacked bugs were found and fixed in the summarizer: the JSON repair prompt
  contained `"..."` placeholders that the 3B model copied literally; chunking
  never split a newline-free 54,556-char paper, so one chunk went far past the
  8192-token context window; and the JATS extractor glued paragraphs together
  with no headings or paragraph breaks. The repair prompt now shows paper
  text with no template values, chunking hard-splits on blank lines, newlines,
  sentences and characters, and JATS `<p>` elements are joined with blank
  lines. Re-run live on the S4 paper (POST /api/v1/europe-pmc/summarize):
  HTTP 200 in 1107.4 s, all four fields populated with real, accurate content
  (problem statement, methodology, key findings, conclusion), zero
  placeholders. Caveats: 18.5 minutes for one full-text paper on this
  CPU-only machine, and the methodology field is capped at 2,000 chars and
  ends mid-sentence. Unit tests are now 44/44.
- Search is fast (1.0-2.8 s per source) and not the bottleneck.
- Backend unit tests: `python -m unittest discover -s src/app/tests -v`
  ran 44 tests, all passed (updated 2026-11-12; was 24 at the time of the
  original run).

## Limitations of this evaluation

- Small sample: 10 questions, 5 papers, 1 run each, no retries.
- Summaries were judged by reading the model output against the paper
  abstract/full text, not by an automated metric.
- Full-PDF calls used the whole extracted PDF text (39-64k chars); the backend
  truncates to the model's 8192-token context, so later pages may not be seen.
- R4/R5 context came from the abstract (R5) or abstract/PDF (R4, not reported
  by the endpoint), so they test abstract-grounded QA more than full-text RAG.
