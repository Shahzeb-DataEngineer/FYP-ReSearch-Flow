// layouts/MainLayout.jsx
import { useCallback, useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import CommandPalette from "../components/CommandPalette";
import Footer from "../components/Footer";
import { Outlet } from "react-router-dom";

/**
 * App shell (Linear-style inverted-L chrome): slim fixed sidebar on
 * desktop (slide-over drawer on mobile), slim sticky top bar with the
 * Cmd+K trigger and theme toggle, content pane, footer.
 */
export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  // Global Cmd/Ctrl+K opens the command palette from anywhere.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="min-h-screen bg-paper text-ink">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="md:pl-60 flex flex-col min-h-screen">
        <Navbar onMenu={() => setSidebarOpen(true)} onOpenPalette={openPalette} />
        <main className="flex-1">
          <Outlet />
        </main>
        <Footer />
      </div>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  );
}
