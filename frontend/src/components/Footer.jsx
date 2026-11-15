import React from "react";

export default function Footer() {
  return (
    <footer className="border-t border-faint bg-surface mt-8">
      <div className="max-w-7xl mx-auto px-6 py-8 text-sm text-muted grid grid-cols-1 md:grid-cols-4 gap-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <img src="/logo.svg" alt="ReSearch Flow logo" className="h-6 w-6 rounded-md" />
            <h2 className="text-base font-semibold text-ink">ReSearch Flow</h2>
          </div>
          <p className="leading-relaxed text-muted">
            AI-powered assistant to explore, understand, and organize research literature using OpenAlex.
          </p>
        </div>

        <div>
          <h3 className="text-xs font-semibold tracking-wide text-muted uppercase mb-3">Product</h3>
          <ul className="space-y-1">
            <li><a href="#" className="hover:text-accent">Overview</a></li>
            <li><a href="#" className="hover:text-accent">Citation mesh</a></li>
            <li><a href="#" className="hover:text-accent">AI summaries</a></li>
            <li><a href="#" className="hover:text-accent">API</a></li>
          </ul>
        </div>

        <div>
          <h3 className="text-xs font-semibold tracking-wide text-muted uppercase mb-3">Resources</h3>
          <ul className="space-y-1">
            <li><a href="#" className="hover:text-accent">Documentation</a></li>
            <li><a href="#" className="hover:text-accent">Changelog</a></li>
            <li><a href="#" className="hover:text-accent">FAQ</a></li>
          </ul>
        </div>

        <div>
          <h3 className="text-xs font-semibold tracking-wide text-muted uppercase mb-3">Connect</h3>
          <ul className="space-y-1">
            <li><a href="#" className="hover:text-accent">Contact</a></li>
            <li><a href="#" className="hover:text-accent">GitHub</a></li>
            <li><a href="#" className="hover:text-accent">Twitter / X</a></li>
          </ul>
        </div>
      </div>

      <div className="border-t border-faint bg-paper">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row items-center justify-between text-xs text-muted">
          <p>
            &copy; {new Date().getFullYear()} ReSearch Flow. Built as an academic project.
          </p>
          <div className="flex items-center gap-4 mt-2 md:mt-0">
            <a href="#" className="hover:text-accent">Privacy</a>
            <a href="#" className="hover:text-accent">Terms</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
