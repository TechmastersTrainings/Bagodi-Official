import React from "react";
import { RefreshCw, ExternalLink, ShieldCheck } from "lucide-react";
import { NavTab } from "./Sidebar";

interface TopHeaderProps {
  activeTab: NavTab;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  systemHealthy?: boolean;
}

const TAB_CONFIG: Record<NavTab, { title: string; subtitle: string }> = {
  users: {
    title: "User Management",
    subtitle: "Customers, boutique merchants, pending merchant approvals, and platform admins",
  },
  products: {
    title: "Product Management",
    subtitle: "Platform-wide apparel catalogue, size-wise stock, categories, and luxury brands",
  },
  orders: {
    title: "Order Management",
    subtitle: "All platform orders, fulfillment packing status, customer shipping, and tracking",
  },
  returns: {
    title: "Return & Exchange Management",
    subtitle: "Customer size swaps, return inspections, boutique restock, and reversals",
  },
  delivery: {
    title: "Delivery Management",
    subtitle: "Logistics fleet, serviceable PIN codes, delivery riders, and dispatch zones",
  },
  coupons: {
    title: "Discount & Coupon Management",
    subtitle: "Promotional vouchers, percentage discounts, minimum spend rules, and caps",
  },
  payments: {
    title: "Payment Management",
    subtitle: "Platform payment ledger, UPI, cards, net banking, Cash on Delivery, and refunds",
  },
};

export const TopHeader: React.FC<TopHeaderProps> = ({
  activeTab,
  onRefresh,
  isRefreshing = false,
  systemHealthy = true,
}) => {
  const current = TAB_CONFIG[activeTab] || TAB_CONFIG.products;

  return (
    <header className="top-header">
      <div className="header-left">
        <h1 className="page-title">{current.title}</h1>
        <p className="page-subtitle">{current.subtitle}</p>
      </div>

      <div className="header-right">
        <a
          href="http://localhost:5174"
          target="_blank"
          rel="noopener noreferrer"
          className="portal-link-btn"
          title="Open live customer shopping experience"
        >
          <span>Storefront</span>
          <ExternalLink size={12} />
        </a>

        <a
          href="http://localhost:5175/merchant"
          target="_blank"
          rel="noopener noreferrer"
          className="portal-link-btn"
          title="Open merchant operations portal"
        >
          <span>Merchant</span>
          <ExternalLink size={12} />
        </a>

        <div className="system-health-pill">
          <span
            className="status-dot"
            style={{
              backgroundColor: systemHealthy ? "#10B981" : "#EF4444",
            }}
          />
          <span>{systemHealthy ? "Database Active" : "Diagnostics"}</span>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Sync latest live platform data from PostgreSQL"
        >
          <RefreshCw size={14} className={isRefreshing ? "spin" : ""} />
          <span>Sync</span>
        </button>
      </div>
    </header>
  );
};
