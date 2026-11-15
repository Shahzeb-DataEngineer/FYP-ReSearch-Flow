import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, BookOpen, Network, Sparkles, ShieldCheck, Wallet } from 'lucide-react';
import SearchBar from '../components/SearchBar';
import ModelPicker from '../components/ModelPicker';
import UsagePanel from '../components/UsagePanel';

const FeatureCard = ({ icon, title, description }) => {
  // Assigned to a const (not a destructured rename): ESLint's
  // no-unused-vars does not count JSX usage of a destructured
  // parameter rename, so `({ icon: Icon })` was wrongly flagged.
  const Icon = icon;
  return (
    <div className="group p-6 bg-surface rounded-2xl border border-faint shadow-soft hover:border-accent/40 hover:shadow-lift hover:-translate-y-0.5 transition-all duration-300 text-left animate-fade-up">
      <div className="flex items-center mb-4">
        <div className="p-3 bg-accent-tint text-accent rounded-xl mr-4 group-hover:scale-110 transition-transform duration-300">
          <Icon className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-semibold text-ink">{title}</h3>
      </div>
      <p className="text-muted leading-relaxed text-[15px]">{description}</p>
    </div>
  );
};

// Honest stats only: every number here is a fact about this project,
// not marketing. Sources, workflows, cost and test count are all
// verifiable from the repo.
const STATS = [
  { value: '10', label: 'Free paper sources', note: 'OpenAlex, arXiv, Semantic Scholar and more' },
  { value: '8', label: 'AI workflows', note: 'Search, summarize, chat, draft, Deep Review, PRISMA, graphs, library' },
  { value: '$0.00', label: 'Total cost', note: 'Local Ollama model, no paid APIs' },
  { value: '156', label: 'Tests passing', note: 'Backend suite, run on every change' },
];

export default function Home() {
  const navigate = useNavigate();

  const handleSearch = (topic) => {
    navigate(`/results?topic=${encodeURIComponent(topic)}`);
  };

  return (
    <div className="min-h-screen bg-paper text-ink overflow-hidden">
      <main className="max-w-7xl mx-auto px-6">
        {/* Hero: question first, like Perplexity - the search box is the hero */}
        <section className="relative pt-16 pb-10 md:pt-24 md:pb-14 text-center">
          {/* Aurora accent - hero only, calm everywhere else */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 -top-24 mx-auto h-96 max-w-4xl overflow-visible">
            <div className="absolute left-[8%] top-10 h-64 w-64 rounded-full bg-teal-400/25 blur-3xl animate-aurora dark:bg-teal-400/20" />
            <div className="absolute right-[10%] top-0 h-56 w-56 rounded-full bg-violet-400/20 blur-3xl animate-aurora dark:bg-violet-500/15" style={{ animationDelay: '-6s' }} />
            <div className="absolute left-1/2 top-24 h-48 w-48 -translate-x-1/2 rounded-full bg-amber-300/20 blur-3xl animate-aurora dark:bg-amber-400/10" style={{ animationDelay: '-3s' }} />
          </div>
          <div className="relative">
          <p className="inline-flex items-center gap-2 text-xs font-semibold tracking-wide uppercase text-accent bg-accent-tint border border-accent-soft rounded-full px-3 py-1.5 mb-6 animate-fade-up">
            <Sparkles className="w-3.5 h-3.5" />
            Free and local - your papers never leave your machine for a paid API
          </p>
          <h1 className="font-display text-4xl md:text-6xl font-semibold leading-[1.1] tracking-tight max-w-3xl mx-auto animate-fade-up" style={{ animationDelay: '60ms' }}>
            Ask a question. Get evidence, not just answers.
          </h1>
          <p className="text-lg text-muted mt-5 mb-10 mx-auto leading-relaxed max-w-2xl animate-fade-up" style={{ animationDelay: '120ms' }}>
            Search across 10 free scholarly sources, summarize papers, chat with
            them, and build drafts where every claim points back to its source.
          </p>

          <div className="mb-6 flex justify-center animate-fade-up" style={{ animationDelay: '180ms' }}>
            <SearchBar onSearch={handleSearch} />
          </div>
          <p className="text-sm text-muted mb-14 animate-fade-up" style={{ animationDelay: '240ms' }}>
            Try: <button type="button" onClick={() => handleSearch('does sleep deprivation impair memory consolidation')} className="text-accent font-medium hover:underline">sleep deprivation and memory</button>
            {' · '}
            <button type="button" onClick={() => handleSearch('transformer attention mechanisms')} className="text-accent font-medium hover:underline">transformer attention</button>
            {' · '}
            <button type="button" onClick={() => handleSearch('CRISPR gene editing ethics')} className="text-accent font-medium hover:underline">CRISPR ethics</button>
            {' · '}
            <span className="inline-flex items-center gap-1 ml-1">
              press <kbd className="px-1.5 py-0.5 text-[11px] font-medium text-muted bg-surface border border-faint rounded-md shadow-soft">⌘K</kbd> anywhere to search
            </span>
          </p>

          {/* Honest stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-5xl mx-auto mb-20 animate-fade-up" style={{ animationDelay: '300ms' }}>
            {STATS.map((stat) => (
              <div key={stat.label} className="bg-surface rounded-2xl border border-faint px-5 py-6 text-center shadow-soft hover:shadow-lift hover:-translate-y-0.5 transition-all duration-300">
                <div className="font-display text-3xl font-semibold text-ink mb-1">{stat.value}</div>
                <div className="text-sm font-medium text-ink">{stat.label}</div>
                <div className="text-xs text-muted mt-1 leading-relaxed">{stat.note}</div>
              </div>
            ))}
          </div>
          </div>
        </section>

        {/* Features */}
        <section className="pb-20">
          <h2 className="font-display text-2xl md:text-3xl font-semibold text-center mb-3">
            Everything a literature review needs
          </h2>
          <p className="text-muted text-center mb-10 max-w-2xl mx-auto">
            From the first search to the finished draft, each step keeps its
            evidence attached, so you can check every claim.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-6xl mx-auto mb-6">
            <FeatureCard
              icon={Search}
              title="Smart Search"
              description="Search across 10 free sources at once with deduplication, so the same paper never shows up twice."
            />
            <FeatureCard
              icon={BookOpen}
              title="Auto Summarization"
              description="Structured summaries of any paper in seconds, run locally on your own machine."
            />
            <FeatureCard
              icon={Network}
              title="Citation Networks"
              description="See how papers connect, find under-cited work, and spot the gaps no one has answered yet."
            />
            <FeatureCard
              icon={Sparkles}
              title="Deep Review"
              description="A full literature review with per-paper extraction and quotes checked against the abstract."
            />
            <FeatureCard
              icon={ShieldCheck}
              title="Verifiable Citations"
              description="Every claim is checked against its source, with retraction and open-access badges on each paper."
            />
            <FeatureCard
              icon={Wallet}
              title="Always $0.00"
              description="No credits, no subscriptions, no per-message meter. The cost panel shows what a cloud model would have charged, and what you actually paid."
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
            <ModelPicker />
            <UsagePanel />
          </div>
        </section>
      </main>
    </div>
  );
}
