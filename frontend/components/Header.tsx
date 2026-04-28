"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useAuth } from "../lib/auth-context";
import { useCart } from "../lib/cart-context";
import { useConfig } from "../lib/config-context";
import { trackEvent } from "../lib/track-event";

interface NavCategory {
  name: string;
  slug: string;
  parent_id: string | null;
}

export default function Header() {
  const { user, isAuthenticated, logout, isLoading } = useAuth();
  const { cart } = useCart();
  const { enable_products, enable_subscriptions } = useConfig();
  const showShopLink = enable_products || enable_subscriptions;
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [navCategories, setNavCategories] = useState<NavCategory[]>([]);

  useEffect(() => {
    async function loadCategories(retries = 2) {
      for (let i = 0; i <= retries; i++) {
        try {
          const r = await fetch("/api/ecommerce/categories");
          if (r.ok) {
            const data: NavCategory[] = await r.json();
            setNavCategories(data.filter((c) => !c.parent_id).slice(0, 5));
            return;
          }
        } catch {
          // Network error — retry
        }
        if (i < retries) await new Promise((r) => setTimeout(r, 1000));
      }
    }
    loadCategories();
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 glass">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2 text-text-primary font-serif text-xl font-bold"
          >
            <span className="gradient-text">Boilerplate</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            {showShopLink && (
              <Link
                href="/products"
                className="text-text-secondary hover:text-text-primary transition-colors text-sm"
              >
                Products
              </Link>
            )}
            {navCategories.map((cat) => (
              <Link
                key={cat.slug}
                href={`/categories/${cat.slug}`}
                className="text-text-secondary hover:text-text-primary transition-colors text-sm"
              >
                {cat.name}
              </Link>
            ))}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-4">
            {/* Cart */}
            <Link
              href="/cart"
              className="relative text-text-secondary hover:text-text-primary transition-colors"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z"
                />
              </svg>
              {cart.item_count > 0 && (
                <span className="absolute -top-2 -right-2 bg-accent-pink text-white text-xs w-5 h-5 flex items-center justify-center rounded-full font-bold">
                  {cart.item_count > 99 ? "99+" : cart.item_count}
                </span>
              )}
            </Link>

            {/* User */}
            {isLoading ? (
              <div className="w-8 h-8 rounded-full bg-glass-bg animate-pulse" />
            ) : isAuthenticated ? (
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-purple to-accent-blue flex items-center justify-center text-white text-xs font-bold">
                    {user?.first_name?.[0] || user?.email[0].toUpperCase()}
                  </div>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>

                {userMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setUserMenuOpen(false)}
                    />
                    <div className="absolute right-0 mt-2 w-56 glass rounded-lg py-2 z-50">
                      <div className="px-4 py-2 border-b border-glass-border">
                        <p className="text-sm text-text-primary font-medium">
                          {user?.first_name} {user?.last_name}
                        </p>
                        <p className="text-xs text-text-muted">{user?.email}</p>
                        <span
                          className={`mt-1 inline-block text-xs px-2 py-0.5 rounded-full ${
                            user?.role === "admin"
                              ? "bg-accent-pink/10 text-accent-pink"
                              : user?.role === "merchant"
                                ? "bg-accent-blue/10 text-accent-blue"
                                : "bg-accent-green/10 text-accent-green"
                          }`}
                        >
                          {user?.role}
                        </span>
                      </div>
                      <Link
                        href="/dashboard"
                        className="block px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-glass-hover transition-colors"
                        onClick={() => setUserMenuOpen(false)}
                      >
                        Dashboard
                      </Link>
                      <Link
                        href="/dashboard/orders"
                        className="block px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-glass-hover transition-colors"
                        onClick={() => setUserMenuOpen(false)}
                      >
                        Orders
                      </Link>
                      <Link
                        href="/dashboard/wishlists"
                        className="block px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-glass-hover transition-colors"
                        onClick={() => setUserMenuOpen(false)}
                      >
                        Wishlists
                      </Link>
                      {user?.role === "merchant" && (
                        <Link
                          href="/merchant/dashboard"
                          className="block px-4 py-2 text-sm text-accent-blue hover:bg-glass-hover transition-colors"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          Merchant Dashboard
                        </Link>
                      )}
                      {user?.role === "customer" && (
                        <Link
                          href="/merchant/register"
                          className="block px-4 py-2 text-sm text-accent-purple hover:bg-glass-hover transition-colors"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          Become a Merchant
                        </Link>
                      )}
                      {user?.role === "admin" && (
                        <Link
                          href="/admin"
                          className="block px-4 py-2 text-sm text-accent-pink hover:bg-glass-hover transition-colors"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          Admin Panel
                        </Link>
                      )}
                      <div className="border-t border-glass-border mt-1 pt-1">
                        <button
                          onClick={() => {
                            trackEvent("logout");
                            logout();
                            setUserMenuOpen(false);
                          }}
                          className="block w-full text-left px-4 py-2 text-sm text-text-muted hover:text-text-primary hover:bg-glass-hover transition-colors"
                        >
                          Sign out
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <Link
                  href="/auth/login"
                  className="text-sm text-text-secondary hover:text-text-primary transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  href="/auth/register"
                  className="btn-primary text-sm !px-4 !py-2"
                >
                  Get Started
                </Link>
              </div>
            )}

            {/* Mobile menu button */}
            <button
              className="md:hidden text-text-secondary hover:text-text-primary"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                {mobileOpen ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-4 border-t border-glass-border">
            <div className="flex flex-col gap-3">
              {showShopLink && (
                <Link
                  href="/products"
                  className="text-text-secondary hover:text-text-primary transition-colors text-sm py-2"
                  onClick={() => setMobileOpen(false)}
                >
                  Products
                </Link>
              )}
              {navCategories.map((cat) => (
                <Link
                  key={cat.slug}
                  href={`/categories/${cat.slug}`}
                  className="text-text-secondary hover:text-text-primary transition-colors text-sm py-2"
                  onClick={() => setMobileOpen(false)}
                >
                  {cat.name}
                </Link>
              ))}
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
