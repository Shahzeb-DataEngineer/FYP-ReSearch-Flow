# ReSearch Flow  
### AI-Powered Academic Research Assistant  

ReSearch Flow is a full-stack AI-driven platform designed to simplify and accelerate the academic literature review process. It integrates multi-source research retrieval, intelligent deduplication, AI summarization, conversational Q&A, citation network visualization, and draft generation into a single unified system.

---

## Problem Statement

Modern research workflows are fragmented across multiple platforms such as Google Scholar, PubMed, and arXiv. Researchers face challenges including:

- Switching between multiple databases  
- Duplicate results across sources  
- Time-consuming paper analysis  
- Lack of visualization for citation relationships  
- No unified AI-assisted research workflow  

---

## Solution

ReSearch Flow provides an **end-to-end research assistant** that:

- Aggregates papers from multiple academic sources  
- Removes duplicates intelligently  
- Generates AI-powered summaries  
- Enables conversational Q&A on papers (RAG)  
- Visualizes citation relationships  
- Assists in research draft writing  

---

## Key Features

### Multi-Source Search
- OpenAlex, arXiv, CORE, PMC, Semantic Scholar, Crossref, Europe PMC  
- Parallel API calls with progressive loading  

### AI Summarization
- Local Ollama model (qwen2.5:7b on a 16 GB laptop, qwen2.5:3b on low-RAM machines)  
- Structured summaries, no paid API key  
- Extracts insights from full PDF content  

### RAG-based Chat
- Ask questions about any paper  
- Hybrid retrieval (local FAISS + BM25, nomic-embed-text)  
- Context-aware responses  

### Citation Mesh
- Interactive graph visualization (Cytoscape.js)  
- Metrics: PageRank, Influence Score, Citation Velocity  

### Draft Generation
- AI-generated structured drafts  
- Uses both text + figures (Vision AI)  

### User Workspace
- Save articles  
- Manage search history  
- Add personal notes  

### Performance Optimization
- Background caching (Supabase)  
- Redis-based chat session storage  

---

## System Architecture
Frontend (React + Vite)
>
Backend (FastAPI)
>
AI Layer (LangChain + local Ollama)
>
Databases (Supabase, local FAISS, Redis)
>
External APIs (OpenAlex, arXiv, etc.)


---

## Tech Stack

### Frontend
- React 19 + Vite  
- Tailwind CSS  
- Framer Motion  
- Cytoscape.js  

### Backend
- FastAPI (Python 3.11)  
- PyMuPDF (PDF parsing)  
- Pandas  

### AI & ML
- Ollama (local, zero cost): qwen2.5:7b / qwen2.5:3b chat, nomic-embed-text embeddings  
- LangChain  
- FAISS (local vector store, per-paper index)  
- BM25 Retriever  

### Database & Storage
- Supabase (PostgreSQL + Auth)  
- Upstash Redis  
- Neo4j (optional)  

---

## Zero-cost note

This project uses no paid APIs. LLM work runs on a local Ollama model,
search uses free sources (OpenAlex, arXiv, CORE, PMC, Semantic Scholar,
Crossref, Europe PMC), and vector search uses local FAISS. Google Scholar
was removed because it needed the paid SerpAPI service.

To run the AI features:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

On a low-RAM machine, use `qwen2.5:3b` instead and set
`OLLAMA_CHAT_MODEL=qwen2.5:3b` in your `.env`. See `.env.example`.

---

## Database Design

The system uses a hybrid approach:

- **Structured Data** → Supabase (users, saved searches, history)  
- **Cached Papers** → research_papers table  
- **Vector Embeddings** → local FAISS (per-paper index)  
- **Session Data** → Redis  

---

## Workflow Overview

1. User enters search query  
2. System queries multiple APIs in parallel  
3. Results are deduplicated  
4. Cached in database  
5. AI modules process data (summary, chat, draft)  
6. Results are displayed with interactive visualizations  

---

## Results & Performance

- ⚡ First results: ~1.8 seconds  
- 🔁 Full results: 6–9 seconds  
- 🧹 Deduplication: ~38% reduction  
- 🤖 RAG Accuracy:  
  - 74% Correct  
  - 18% Partial  
  - 8% Incorrect  

---

## Authentication

- Supabase Auth (JWT-based)  
- Google OAuth support  
- Row-Level Security (RLS)  

---

## Testing

- Unit testing for all core modules  
- Integration testing for full workflows  
- Manual evaluation with real academic datasets  

---

## Limitations

- Requires open-access PDFs for full AI analysis  
- API rate limits on free sources  
- Initial RAG indexing delay for new papers  

---

## Future Work

- Semantic vector search (Sentence-BERT)  
- Multi-modal RAG (text + figures)  
- Chrome extension  
- Collaborative research workspace  
- Mobile app  
- OCR for scanned PDFs  

---

## Team

- **Haroon Mahmood (BSDSF22M020@pucit.edu.pk)**  
- **Maryam Abid (BSDSF22M028pucit.edu.pk)**  
- **Areesha Rizwan (BSDSF22M048pucit.edu.pk)**  
- **Shahzeb Ali (BSDSF22M054pucit.edu.pk)**  

---

## Supervisor

**Dr. Khurram Shahzad**  
Faculty of Computing & Information Technology  
University of the Punjab, Lahore  

---

## License

This project is developed for academic purposes as a Final Year Project.  

The system follows a modular layered architecture:
