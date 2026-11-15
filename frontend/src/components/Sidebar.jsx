import { useEffect, useState } from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import {
  Search, FileCheck2, Network, Library, Bookmark, Crown, X, Wallet,
} from 'lucide-react';
import { modelsAPI } from '../services/api';

const NAV_ITEMS = [
  { to: '/', label: 'Search', icon: Search, end: true },
  { to: '/prisma', label: 'PRISMA Review', icon: FileCheck2 },
  { to: '/citation-graph', label: 'Citation Graph', icon: Network },
  { to: '/my-library', label: 'My Library', icon: Library },
  { to: '/saved-searches', label: 'Saved Searches', icon: Bookmark },
  { to: '/pricing', label: 'Pricing', icon: Crown },
];

/**
 * Slim app sidebar (Linear-style inverted-L chrome): logo, main sections,
 * and a compact model + cost footer. Fixed on desktop, slide-over drawer
 * on mobile.
 */
export default function Sidebar({ open, onClose }) {
  const navigate = useNavigate();
  const [modelName, setModelName] = useState('');
  const [totalSpent, setTotalSpent] = useState(null);

  useEffect(() => {
    let cancelled = false;
    modelsAPI.listModels()
      .then((data) => {
        if (!cancelled && data?.active_chat_model) setModelName(data.active_chat_model);
      })
      .catch(() => {});
    modelsAPI.getUsage()
      .then((data) => {
        if (!cancelled && typeof data?.total_spent_usd !== 'undefined') {
          setTotalSpent(data.total_spent_usd);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden animate-fade-in"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 w-60 flex flex-col bg-surface border-r border-faint transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          <Link
            to="/"
            onClick={onClose}
            className="flex items-center gap-2.5 hover:opacity-80 transition-opacity min-w-0"
          >
            <img className="h-8 w-8 shrink-0 rounded-lg shadow-soft" src="/logo.svg" alt="ReSearch Flow" />
            <span className="min-w-0">
              <span className="block text-[15px] font-semibold text-ink leading-tight truncate">
                ReSearch <span className="text-accent">Flow</span>
              </span>
              <span className="block text-[11px] text-muted leading-tight">AI Research Assistant</span>
            </span>
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="p-1.5 rounded-lg text-muted hover:text-ink hover:bg-fill transition-colors md:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5" aria-label="Main">
          <p className="px-2 pt-1 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
            Research
          </p>
          {NAV_ITEMS.slice(0, 5).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) => `group flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-accent-tint text-accent'
                    : 'text-ink-soft hover:bg-fill hover:text-ink'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}

          <p className="px-2 pt-4 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
            Account
          </p>
          {NAV_ITEMS.slice(5).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) => `group flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-accent-tint text-accent'
                    : 'text-ink-soft hover:bg-fill hover:text-ink'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Footer: local model + cost, always $0.00 */}
        <div className="p-3 border-t border-faint">
          <button
            type="button"
            onClick={() => { onClose(); navigate('/'); }}
            className="w-full text-left rounded-xl border border-faint bg-fill px-3 py-2.5 hover:border-accent/40 transition-colors group"
            title="Local model - change it on the home page"
          >
            <span className="flex items-center gap-2 text-xs font-semibold text-ink">
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-success" />
              </span>
              Local model
            </span>
            <span className="mt-1 block truncate font-mono text-xs text-muted">
              {modelName || 'qwen2.5:3b'}
            </span>
            <span className="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
              <Wallet className="w-3.5 h-3.5 text-success" />
              <span>
                Total spent: <span className="font-semibold text-success">$0.00</span>
                {totalSpent !== null && totalSpent !== 0 ? ` (reported ${totalSpent})` : ''}
              </span>
            </span>
          </button>
          <p className="mt-2 px-1 text-[11px] leading-relaxed text-muted">
            Runs on your machine. No paid APIs, ever.
          </p>
        </div>
      </aside>
    </>
  );
}
