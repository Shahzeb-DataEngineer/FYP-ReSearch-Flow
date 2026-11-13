import React, { useState, useEffect, useRef } from "react";
import { NavLink, useNavigate, Link } from "react-router-dom";
import researchLogo from "../assets/researchLogo.jpg";
import { Menu, LogOut, Bookmark, Crown, ArrowUpRight } from "lucide-react";
import { useAuth } from "../hooks/useAuth";

export default function Navbar() {
  const [, setVisible] = useState(false);
  const [userMenuVisible, setUserMenuVisible] = useState(false);
  const { user, isAuthenticated, signOut, loading } = useAuth();
  const userPlan = (user?.user_metadata?.plan || "basic").toLowerCase();

  const menuRef = useRef(null);
  const buttonRef = useRef(null);
  const userMenuRef = useRef(null);
  const userButtonRef = useRef(null);
  const navigate = useNavigate();

  // Handle clicks outside menus
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target)
      ) {
        setVisible(false);
      }
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

  const handleSavedSearches = () => {
    navigate("/saved-searches");
    setUserMenuVisible(false);
  };

  const handlePricing = () => navigate("/pricing");

  const handleUpgrade = () => {
    setUserMenuVisible(false);
    navigate("/pricing");
  };

  const getUserInitials = (user) => {
    if (!user) return "U";
    const name = user.user_metadata?.full_name || user.email;
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

  const getUserDisplayName = (user) => {
    if (!user) return "User";
    return (
      user.user_metadata?.full_name ||
      user.email?.split("@")[0] ||
      "User"
    );
  };

  const NavButton = ({ children, primary = false, onClick }) => (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors border ${
        primary
          ? "bg-black text-white border-black hover:bg-gray-800"
          : "text-gray-700 border-transparent hover:border-gray-300 hover:bg-gray-100"
      }`}
    >
      {children}
    </button>
  );

  const UserAvatar = ({ user, onClick }) => (
    <button
      ref={userButtonRef}
      onClick={onClick}
      className="flex items-center space-x-2 px-2 py-1.5 rounded-full hover:bg-gray-100 transition-all duration-200"
    >
      <div className="w-10 h-10 bg-black rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
        {user?.user_metadata?.avatar_url ? (
          <img
            src={user.user_metadata.avatar_url}
            alt={getUserDisplayName(user)}
            className="w-10 h-10 rounded-full object-cover"
          />
        ) : (
          getUserInitials(user)
        )}
      </div>
      <span className="text-gray-700 text-sm font-medium hidden sm:block max-w-[100px] truncate">
        {getUserDisplayName(user)}
      </span>
    </button>
  );

  const UserMenu = () => (
    <div
      ref={userMenuRef}
      className="absolute right-0 mt-2 min-w-max py-2 bg-white rounded-lg shadow-lg border border-gray-200 z-50"
    >
      <div className="px-4 py-2 border-b border-gray-100">
        <p className="text-sm font-medium text-gray-900 whitespace-nowrap">
          {getUserDisplayName(user)}
        </p>
        <p className="text-sm text-gray-500 whitespace-nowrap">{user?.email}</p>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-gray-600 whitespace-nowrap">
            Current plan: {userPlan.charAt(0).toUpperCase() + userPlan.slice(1)}
          </span>
          {["basic", "premium"].includes(userPlan) && (
            <button
              onClick={handleUpgrade}
              className="text-xs px-2 py-1 border border-green-500 text-green-600 rounded-full hover:bg-green-50 transition-colors"
            >
              Upgrade
            </button>
          )}
        </div>
      </div>

      <button
        onClick={handleSavedSearches}
        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
      >
        <Bookmark className="w-4 h-4" />
        <span>Saved Searches</span>
      </button>

      <hr className="my-1 border-gray-500"/>

      <button
        onClick={handleLogout}
        className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
      >
        <LogOut className="w-4 h-4" />
        <span>Sign out</span>
      </button>
    </div>
  );

  if (loading) {
    return (
      <header className="border-b border-gray-200 bg-white relative z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 flex items-center justify-center">
              <img className="rounded-lg" src={researchLogo} alt="ReSearch Flow" />
            </div>
            <div className="hidden md:block">
              <h1 className="text-lg font-semibold text-black">ReSearch Flow</h1>
              <p className="text-xs text-gray-500">AI Research Assistant</p>
            </div>
          </div>
          <div className="w-20 h-6 bg-gray-200 rounded-full animate-pulse"></div>
        </div>
      </header>
    );
  }

  return (
    <header className="border-b border-gray-200 bg-white relative z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <Link to="/" className="flex items-center space-x-3 hover:opacity-80 transition-opacity">
        <div className="w-9 h-9 flex items-center justify-center">
          <img className="rounded-lg" src={researchLogo} alt="ReSearch Flow" />
        </div>
        <div className="hidden md:block">
          <h1 className="text-lg font-semibold text-black">ReSearch Flow</h1>
          <p className="text-xs text-gray-500">AI Research Assistant</p>
        </div>
      </Link>

      

      <div className="flex items-center space-x-2">
        <button
          onClick={handlePricing}
          className="hidden sm:inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-black rounded-full border border-transparent hover:border-gray-300 hover:bg-gray-100 transition-colors"
        >
          <Crown className="w-4 h-4" />
          Pricing
        </button>
        {isAuthenticated ? (
          <div className="relative">
            <UserAvatar
              user={user}
              onClick={() => setUserMenuVisible(!userMenuVisible)}
            />
            {userMenuVisible && <UserMenu />}
          </div>
        ) : (
          <div className="space-x-6">
            <button
              onClick={handleLogin}
              className="text-sm text-gray-700 hover:text-black"
            >
              Log in
            </button>
            <NavButton primary onClick={handleSignUp}>Sign up</NavButton>
          </div>
        )}
      </div>

      
    </div>
    </header>
  );
}
