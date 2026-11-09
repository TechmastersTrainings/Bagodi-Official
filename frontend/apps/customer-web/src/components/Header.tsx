import { Search, X, ShoppingBag, User, MapPin } from "lucide-react";
import type { AuthUser } from "@bagodi/api-client";

interface HeaderProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  cartCount: number;
  currentUser: AuthUser | null;
  onOpenAuth: () => void;
  onOpenCart?: () => void;
}

export function Header({
  searchQuery,
  onSearchChange,
  cartCount,
  currentUser,
  onOpenAuth,
  onOpenCart,
}: HeaderProps) {
  return (
    <>
      <div className="top-notice-bar">
        <span className="pill">Bidar Store</span>
        <span>Fresh fruits, vegetables, groceries & essentials • Delivered to your doorstep in Bidar</span>
      </div>

      <header className="main-header">
        <div className="header-inner">
          <div className="brand-section">
            <a href="/" className="brand-logo" aria-label="Bagodi Home">
              <span>Bagodi</span>
              <span className="brand-dot" />
            </a>

            <div className="location-badge">
              <MapPin size={14} color="var(--color-terracotta)" />
              <span>Bidar, Karnataka • <strong>Express 2-Hr</strong></span>
            </div>
          </div>

          <div className="search-container">
            <div className="search-input-wrapper">
              <Search size={18} className="search-icon" />
              <input
                type="text"
                className="search-input"
                placeholder="Search fresh produce, staples, dairy..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                aria-label="Search catalogue"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="search-clear-btn"
                  onClick={() => onSearchChange("")}
                  aria-label="Clear search"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          <div className="header-actions">
            <button
              type="button"
              className={`btn-header-auth ${currentUser ? "authenticated" : ""}`}
              onClick={onOpenAuth}
              aria-label={currentUser ? "Account profile" : "Sign in"}
            >
              <User size={18} />
              <span>
                {currentUser?.full_name || (currentUser?.phone ? currentUser.phone.slice(-4) : "Sign In")}
              </span>
            </button>

            <button
              type="button"
              className="btn-cart"
              onClick={onOpenCart}
              aria-label={`Shopping cart with ${cartCount} items`}
            >
              <ShoppingBag size={20} />
              {cartCount > 0 && <span className="cart-count-badge">{cartCount}</span>}
            </button>
          </div>
        </div>
      </header>
    </>
  );
}
