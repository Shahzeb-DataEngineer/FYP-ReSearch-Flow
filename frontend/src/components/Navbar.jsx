import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, LogOut, Bookmark, Crown, Search, Sun, Moon } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";

/**
 * Slim top bar (Linear-style inverted-L chrome): mobile menu button,
 * Cmd+K quick-search trigger, theme toggle, and the user menu.
 * Main navigation lives in the sidebar.
 */
export default function Navbar({ onMenu, onOpenPalette }) {
  const [userMenuVisible, setUserMenuVisible] = useState(false);
  const { user, isAuthenticated, signOut, loading } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const userPlan = (user?.user_metadata?.plan || "basic").toLowerCase();

  const userMenuRef = useRef(null);
  const userButtonRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target) &&
        userButtonRef.current &&
        !userButtonRef.current.contains(event.target)
      ) {
        setUserMenuVisible(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogin = () => navigate("/auth?mode=login");
  const handleSignUp = () => navigate("/auth?mode=signup");

  const handleLogout = async () => {
    try {
      await signOut();
      setUserMenuVisible(false);
      navigate("/");
    } catch (error) {
      console.error("Error signing out:", error);
    }
  };

  const getUserInitials = (u) => {
    if (!u) return "U";
    const name = u.user_metadata?.full_name || u.email;
    if (name) {
      return name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);
    }
    return "U";
  };

  const getUserDisplayName = (u) => {
    if (!u) return "User";
    return u.user_metadata?.full_name || u.email?.split("@")[0] || "User";
  };

  return (
    <header className="sticky top-0 z-40 border-b border-faint bg-surface/80 backdrop-blur-md">
      <div className="flex items-center gap-2 px-3 sm:px-4 py-2.5">
        <button
          type="button"
          onClick={onMenu}
          aria-label="Open menu"
          className="p-2 -ml-1 rounded-lg text-muted hover:text-ink hover:bg-fill transition-colors md:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Cmd+K quick search trigger */}
        <button
          type="button"
          onClick={onOpenPalette}
          className="flex-1 max-w-md flex items-center gap-2.5 px-3 py-2 rounded-lg border border-faint bg-fill text-sm text-muted hover:text-ink hover:border-accent/40 transition-all duration-150 text-left"
        >
          <Search className="w-4 h-4 shrink-0" />
          <span className="flex-1 truncate hidden sm:inline">Search papers, or jump to...</span>
          <span className="flex-1 truncate sm:hidden">Search...</span>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[11px] font-medium text-muted bg-surface border border-faint rounded-md">
            ⌘K
          </kbd>
        </button>

        <div className="flex-1" />

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className="p-2 rounded-lg text-muted hover:text-ink hover:bg-fill transition-colors"
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        {loading ? (
          <div className="w-9 h-9 rounded-full bg-fill animate-pulse" />
        ) : isAuthenticated ? (
          <div className="relative">
            <button
              ref={userButtonRef}
              onClick={() => setUserMenuVisible(!userMenuVisible)}
              className="flex items-center gap-2 p-1 rounded-full hover:bg-fill transition-colors"
              aria-label="Account menu"
            >
              <span className="w-8 h-8 bg-accent rounded-full flex items-center justify-center text-white text-xs font-semibold shrink-0 overflow-hidden">
                {user?.user_metadata?.avatar_url ? (
                  <img
                    src={user.user_metadata.avatar_url}
                    alt={getUserDisplayName(user)}
                    className="w-8 h-8 rounded-full object-cover"
                  />
                ) : (
                  getUserInitials(user)
                )}
              </span>
              <span className="text-sm font-medium text-ink-soft hidden lg:block max-w-[100px] truncate">
                {getUserDisplayName(user)}
              </span>
            </button>
            {userMenuVisible && (
              <div
                ref={userMenuRef}
                className="absolute right-0 mt-2 min-w-max py-2 bg-surface rounded-2xl shadow-lift border border-faint z-50 animate-fade-up"
              >
                <div className="px-4 py-2 border-b border-faint">
                  <p className="text-sm font-medium text-ink whitespace-nowrap">
                    {getUserDisplayName(user)}
                  </p>
                  <p className="text-sm text-muted whitespace-nowrap">{user?.email}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-xs text-muted whitespace-nowrap">
                      Current plan: {userPlan.charAt(0).toUpperCase() + userPlan.slice(1)}
                    </span>
                    {["basic", "premium"].includes(userPlan) && (
                      <button
                        onClick={() => { setUserMenuVisible(false); navigate("/pricing"); }}
                        className="text-xs px-2 py-1 border border-accent text-accent rounded-full hover:bg-accent-tint transition-colors"
                      >
                        Upgrade
                      </button>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => { navigate("/saved-searches"); setUserMenuVisible(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-ink-soft hover:bg-fill flex items-center space-x-2 transition-colors"
                >
                  <Bookmark className="w-4 h-4" />
                  <span>Saved Searches</span>
                </button>
                <button
                  onClick={() => { navigate("/pricing"); setUserMenuVisible(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-ink-soft hover:bg-fill flex items-center space-x-2 transition-colors"
                >
                  <Crown className="w-4 h-4" />
                  <span>Pricing</span>
                </button>
                <hr className="my-1 border-faint" />
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2 text-left text-sm text-danger hover:bg-danger-soft flex items-center space-x-2 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-1 sm:gap-2">
            <button
              onClick={handleLogin}
              className="px-3 py-1.5 text-sm font-medium text-ink-soft hover:text-accent rounded-full transition-colors"
            >
              Log in
            </button>
            <button
              onClick={handleSignUp}
              className="px-3.5 py-1.5 text-sm font-medium bg-accent text-white rounded-full hover:bg-accent-hover transition-colors shadow-soft"
            >
              Sign up
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
