import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, Home, FileCheck2, Network, Library, Bookmark, Crown,
  Moon, Sun, Clock, TrendingUp, CornerDownLeft, Sparkles,
} from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { useSearchHistory } from '../hooks/useSearchHistory';

/**
 * Command palette (Cmd/Ctrl+K) - Linear/Raycast style quick launcher.
 * Frontend-only: navigates to routes, toggles the theme, and searches
 * via the existing search-history suggestions (local + OpenAlex).
 * No backend changes.
 */
export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { searchHistory, getSuggestions } = useSearchHistory();
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [highlighted, setHighlighted] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // Focus the input whenever the palette opens, and reset state.
  useEffect(() => {
    if (open) {
      setQuery('');
      setSuggestions([]);
      setHighlighted(0);
      const t = setTimeout(() => inputRef.current?.focus(), 30);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [open ]);

  // Live suggestions for the typed query (debounced).
  useEffect(() => {
    if (!open) return undefined;
    const q = query.trim();
    if (q.length === 0) {
      setSuggestions([]);
      return undefined;
    }
    const t = setTimeout(async () => {
      try {
        const results = await getSuggestions(q, 6);
        setSuggestions(results || []);
      } catch {
        setSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [query, open, getSuggestions]);

  const actions = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = [
      { id: 'home', label: 'New search', hint: 'Home', icon: Home, run: () => navigate('/') },
      { id: 'prisma', label: 'Go to PRISMA Review', hint: 'Systematic review', icon: FileCheck2, run: () => navigate('/prisma') },
      { id: 'graph', label: 'Go to Citation Graph', hint: 'Gap finder', icon: Network, run: () => navigate('/citation-graph') },
      { id: 'library', label: 'Go to My Library', hint: 'Saved papers', icon: Library, run: () => navigate('/my-library') },
      { id: 'saved', label: 'Go to Saved Searches', hint: 'History', icon: Bookmark, run: () => navigate('/saved-searches') },
      { id: 'pricing', label: 'Go to Pricing', hint: 'Plans', icon: Crown, run: () => navigate('/pricing') },
      {
        id: 'theme', label: theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode',
        hint: 'Theme', icon: theme === 'dark' ? Sun : Moon, run: toggleTheme,
      },
    ];
    if (!q) return all;
    return all.filter((a) => a.label.toLowerCase().includes(q) || a.hint.toLowerCase().includes(q));
  }, [query, navigate, theme, toggleTheme]);

  const searchItems = useMemo(() => {
    const q = query.trim();
    if (q.length === 0) {
      return (searchHistory || []).slice(0, 5).map((entry) => ({
        id: `history-${entry.id || entry.query}`,
        label: entry.query,
        hint: 'Recent search',
        icon: Clock,
        run: () => navigate(`/results?topic=${encodeURIComponent(entry.query)}`),
      }));
    }
    const seen = new Set();
    return (suggestions || [])
      .filter((s) => {
        const key = (s.text || '').toLowerCase();
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 6)
      .map((s, i) => ({
        id: `suggestion-${i}`,
        label: s.text,
        hint: s.type === 'history' ? 'Recent search' : s.hint || 'Search papers',
        icon: s.type === 'history' ? Clock : TrendingUp,
        run: () => navigate(`/results?topic=${encodeURIComponent(s.text)}`),
      }));
  }, [query, searchHistory, suggestions, navigate]);

  // Flat list for keyboard navigation: search action first, then actions, then items.
  const items = useMemo(() => {
    const list = [];
    if (query.trim().length > 0) {
      list.push({
        id: 'search-query', label: `Search papers for "${query.trim()}"`, hint: 'Search',
        icon: Search, run: () => navigate(`/results?topic=${encodeURIComponent(query.trim())}`),
      });
    }
    actions.forEach((a) => list.push({ ...a, group: 'Actions' }));
    searchItems.forEach((s) => list.push({ ...s, group: query.trim() ? 'Suggestions' : 'Recent searches' }));
    return list;
  }, [query, actions, searchItems, navigate]);

  useEffect(() => {
    setHighlighted(0);
  }, [items.length, query]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlighted((h) => (items.length === 0 ? 0 : (h + 1) % items.length));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlighted((h) => (items.length === 0 ? 0 : (h - 1 + items.length) % items.length));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const item = items[highlighted];
        if (item) {
          onClose();
          item.run();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, items, highlighted, onClose]);

  // Keep the highlighted row visible.
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${highlighted}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlighted]);

  if (!open) return null;

  let lastGroup = null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[12vh] bg-black/40 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg bg-surface border border-faint rounded-2xl shadow-lift overflow-hidden animate-fade-up">
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-faint">
          <Search className="w-5 h-5 text-muted shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search papers, or jump to a section..."
            className="flex-1 bg-transparent text-ink placeholder-muted focus:outline-none text-[15px]"
            aria-label="Command palette"
          />
          <kbd className="shrink-0 px-1.5 py-0.5 text-[11px] font-medium text-muted bg-fill border border-faint rounded-md">ESC</kbd>
        </div>

        <div ref={listRef} className="max-h-[46vh] overflow-y-auto py-1.5">
          {items.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <Sparkles className="w-5 h-5 text-muted mx-auto mb-2" />
              <p className="text-sm text-muted">
                {query.trim() ? 'Nothing matches that yet. Press Enter to search it anyway.' : 'Type to search papers or jump anywhere.'}
              </p>
            </div>
          ) : (
            items.map((item, idx) => {
              const Icon = item.icon;
              const groupHeader = item.group && item.group !== lastGroup
                ? (() => { lastGroup = item.group; return item.group; })()
                : null;
              return (
                <div key={item.id}>
                  {groupHeader && (
                    <p className="px-4 pt-2.5 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
                      {groupHeader}
                    </p>
                  )}
                  <button
                    type="button"
                    data-idx={idx}
                    onMouseEnter={() => setHighlighted(idx)}
                    onClick={() => {
                      onClose();
                      item.run();
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                      highlighted === idx ? 'bg-accent-tint' : ''
                    }`}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${highlighted === idx ? 'text-accent' : 'text-muted'}`} />
                    <span className="flex-1 truncate text-sm text-ink">{item.label}</span>
                    {item.hint && (
                      <span className="text-xs text-muted shrink-0 max-w-[140px] truncate">{item.hint}</span>
                    )}
                    {highlighted === idx && (
                      <CornerDownLeft className="w-3.5 h-3.5 text-muted shrink-0" />
                    )}
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-faint text-[11px] text-muted">
          <span><kbd className="px-1 py-0.5 bg-fill border border-faint rounded">↑↓</kbd> navigate</span>
          <span><kbd className="px-1 py-0.5 bg-fill border border-faint rounded">↵</kbd> select</span>
          <span><kbd className="px-1 py-0.5 bg-fill border border-faint rounded">esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
