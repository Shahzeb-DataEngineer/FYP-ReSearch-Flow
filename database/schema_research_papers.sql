-- Create research_papers table for storing fetched academic papers
-- Columns match exactly what backend/src/app/crud/papers_crud.py
-- (store_to_supabase) writes via upsert, and what
-- frontend/src/pages/Results.jsx inserts when caching search results.
-- The upsert uses paperid as the conflict target, so paperid is the
-- primary key.
--
-- How to apply: copy this file into the Supabase SQL Editor and run it.
-- It is safe to re-run: the table and indexes are created only if they
-- do not already exist.
--
-- Note: Row Level Security is intentionally NOT enabled here. This table
-- holds public paper data and is written both by the backend and by the
-- frontend using the Supabase anon key (see Results.jsx saveToCache).
-- Enabling RLS without matching policies would break those writes.
-- If RLS is enabled later, add policies that allow anon select/insert
-- (and update for upserts) or the existing cache paths will fail.
--
-- Note: database/add_institutions_column.sql is now redundant, since
-- the institutions column is included below. It is kept for history.

CREATE TABLE IF NOT EXISTS research_papers (
    paperid TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'N/A',
    abstract TEXT,
    authors JSONB NOT NULL DEFAULT '[]'::jsonb,
    url TEXT,
    year INTEGER,
    venue TEXT,
    publicationtypes JSONB NOT NULL DEFAULT '[]'::jsonb,
    citationcount INTEGER NOT NULL DEFAULT 0,
    referencecount INTEGER NOT NULL DEFAULT 0,
    referencedworks JSONB NOT NULL DEFAULT '[]'::jsonb,
    isopenaccess BOOLEAN NOT NULL DEFAULT FALSE,
    openaccesspdf TEXT,
    externalids JSONB NOT NULL DEFAULT '{}'::jsonb,
    fieldsofstudy JSONB NOT NULL DEFAULT '[]'::jsonb,
    institutions JSONB NOT NULL DEFAULT '[]'::jsonb,
    source TEXT,
    topic TEXT,
    content TEXT,
    inserted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for the lookups used by the app:
-- topic is filtered on every cache check (Results.jsx checkCache)
-- and by the citation mesh endpoint; year and source are common filters.
CREATE INDEX IF NOT EXISTS idx_research_papers_topic ON research_papers(topic);
CREATE INDEX IF NOT EXISTS idx_research_papers_year ON research_papers(year);
CREATE INDEX IF NOT EXISTS idx_research_papers_source ON research_papers(source);
CREATE INDEX IF NOT EXISTS idx_research_papers_citationcount ON research_papers(citationcount DESC);

-- GIN indexes for the JSONB array columns queried by containment.
CREATE INDEX IF NOT EXISTS idx_research_papers_fieldsofstudy ON research_papers USING GIN (fieldsofstudy);
CREATE INDEX IF NOT EXISTS idx_research_papers_institutions ON research_papers USING GIN (institutions);
