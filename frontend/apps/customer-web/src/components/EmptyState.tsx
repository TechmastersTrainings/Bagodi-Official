import { ShoppingBag, Search, Sparkles } from "lucide-react";

interface EmptyStateProps {
  isSearch: boolean;
  isCategoryFilter: boolean;
  searchQuery?: string;
  onReset: () => void;
}

export function EmptyState({ isSearch, isCategoryFilter, searchQuery, onReset }: EmptyStateProps) {
  return (
    <div className="empty-state-container" role="status">
      <div className="empty-icon-wrap">
        {isSearch ? <Search size={28} /> : <ShoppingBag size={28} />}
      </div>

      <h3 className="empty-title">
        {isSearch
          ? `No matches for "${searchQuery}"`
          : isCategoryFilter
          ? "No items in this category yet"
          : "Welcome to Bagodi Bidar"}
      </h3>

      <p className="empty-description">
        {isSearch
          ? "Check your spelling or try searching for another everyday grocery or fresh produce item."
          : isCategoryFilter
          ? "Our Bidar fulfillment team is actively inwarding new inventory for this category."
          : "Your local storefront is running live. Products will appear here as soon as they are stocked and published by our Bidar store team."}
      </p>

      {(isSearch || isCategoryFilter) ? (
        <button
          type="button"
          className="btn-primary-action"
          onClick={onReset}
          style={{ width: "auto", padding: "8px 20px" }}
        >
          View All Available Items
        </button>
      ) : (
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "0.8125rem", color: "var(--color-botanical)", fontWeight: 600 }}>
          <Sparkles size={16} /> Zero dummy data policy active
        </div>
      )}
    </div>
  );
}
