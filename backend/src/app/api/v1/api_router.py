from fastapi import APIRouter
from src.app.api.v1.routes.search import router as search_router
from src.app.api.v1.routes.papers import router as papers_router
from src.app.api.v1.routes.citation import router as citation_router
from src.app.api.v1.routes.arxiv import router as arxiv_router
from src.app.api.v1.routes.core import router as core_router
from src.app.api.v1.routes.pmc import router as pmc_router
from src.app.api.v1.routes.semantic_scholar import router as semantic_scholar_router
from src.app.api.v1.routes.crossref import router as crossref_router
from src.app.api.v1.routes.europe_pmc import router as europe_pmc_router
from src.app.api.v1.routes.pubmed import router as pubmed_router
from src.app.api.v1.routes.doaj import router as doaj_router
from src.app.api.v1.routes.unpaywall import router as unpaywall_router
from src.app.api.v1.routes.trends import router as trends_router
from src.app.api.v1.routes.draft import router as draft_router
from src.app.api.v1.routes.chat import router as chat_router
from src.app.api.v1.routes.review import router as review_router
from src.app.api.v1.routes.citations import router as citations_router
from src.app.api.v1.routes.fulltext import router as fulltext_router
from src.app.api.v1.routes.gap_finder import router as gap_finder_router
from src.app.api.v1.routes.library import router as library_router

api_router = APIRouter()

api_router.include_router(search_router, prefix="/search", tags=["Search"])
api_router.include_router(papers_router, prefix="/papers", tags=["Papers"])
api_router.include_router(citation_router, prefix="/citation", tags=["Citation Network"])
api_router.include_router(arxiv_router, prefix="/arxiv", tags=["arXiv Search & Summarization"])
api_router.include_router(core_router, prefix="/core", tags=["CORE Search & Summarization"])
api_router.include_router(pmc_router, prefix="/pmc", tags=["PMC Search & Summarization"])
api_router.include_router(semantic_scholar_router, prefix="/semantic-scholar", tags=["Semantic Scholar Search & Summarization"])
api_router.include_router(crossref_router, prefix="/crossref", tags=["Crossref Search & Summarization"])
api_router.include_router(europe_pmc_router, prefix="/europe-pmc", tags=["Europe PMC Search & Summarization"])
api_router.include_router(pubmed_router, prefix="/pubmed", tags=["PubMed Search & Summarization"])
api_router.include_router(doaj_router, prefix="/doaj", tags=["DOAJ Search & Summarization"])
api_router.include_router(unpaywall_router, prefix="/unpaywall", tags=["Unpaywall Search & Summarization"])
api_router.include_router(trends_router, prefix="/trends", tags=["Trending Topics"])
api_router.include_router(draft_router, prefix="/draft", tags=["Draft Generation"])
api_router.include_router(chat_router, prefix="/chat", tags=["Paper Chat (RAG)"])
api_router.include_router(review_router, prefix="/review", tags=["Deep Review"])
api_router.include_router(citations_router, prefix="/citations", tags=["Citation Verification"])
api_router.include_router(fulltext_router, prefix="/papers", tags=["Full Text"])
api_router.include_router(gap_finder_router, prefix="/gap-finder", tags=["Citation Graph and Gap Finder"])
api_router.include_router(library_router, prefix="/library", tags=["Private Knowledge Graph"])
