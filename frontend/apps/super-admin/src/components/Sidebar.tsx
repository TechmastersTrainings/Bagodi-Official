import React from "react";
import {
  Users,
  Shirt,
  ShoppingBag,
  RotateCcw,
  Truck,
  Tag,
  CreditCard,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { PlatformUser } from "../types";

export type NavTab =
  | "users"
  | "products"
  | "orders"
  | "returns"
  | "delivery"
  | "coupons"
  | "payments";

interface SidebarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  staffUser: PlatformUser | null;
  pendingMerchantsCount: number;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  staffUser,
  pendingMerchantsCount,
  onLogout,
}) => {
  return (
    <aside className="app-sidebar">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand-badge">
          <div className="brand-logo-icon">
            <ShieldCheck size={20} color="#FFFFFF" />
          </div>
          <div>
            <div className="brand-title">Bagodi</div>
            <div className="brand-sub">Platform Administration</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="nav-section-title" style={{ color: "var(--text-muted)", fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Core Commerce Modules
        </div>

        <button
          className={`nav-item ${activeTab === "users" ? "active" : ""}`}
          onClick={() => onSelectTab("users")}
        >
          <div className="nav-item-left">
            <Users size={18} />
            <span>User Management</span>
          </div>
          {pendingMerchantsCount > 0 && (
            <span className="badge danger" title={`${pendingMerchantsCount} pending boutique approvals`}>
              {pendingMerchantsCount}
            </span>
          )}
        </button>

        <button
          className={`nav-item ${activeTab === "products" ? "active" : ""}`}
          onClick={() => onSelectTab("products")}
        >
          <div className="nav-item-left">
            <Shirt size={18} />
            <span>Product Management</span>
          </div>
        </button>

        <button
          className={`nav-item ${activeTab === "orders" ? "active" : ""}`}
          onClick={() => onSelectTab("orders")}
        >
          <div className="nav-item-left">
            <ShoppingBag size={18} />
            <span>Order Management</span>
          </div>
        </button>

        <button
          className={`nav-item ${activeTab === "returns" ? "active" : ""}`}
          onClick={() => onSelectTab("returns")}
        >
          <div className="nav-item-left">
            <RotateCcw size={18} />
            <span>Return / Exchange</span>
          </div>
        </button>

        <button
          className={`nav-item ${activeTab === "delivery" ? "active" : ""}`}
          onClick={() => onSelectTab("delivery")}
        >
          <div className="nav-item-left">
            <Truck size={18} />
            <span>Delivery Management</span>
          </div>
        </button>

        <div className="nav-section-title" style={{ color: "var(--text-muted)", fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: "1rem" }}>
          Finance &amp; Promotions
        </div>

        <button
          className={`nav-item ${activeTab === "coupons" ? "active" : ""}`}
          onClick={() => onSelectTab("coupons")}
        >
          <div className="nav-item-left">
            <Tag size={18} />
            <span>Discount &amp; Coupons</span>
          </div>
        </button>

        <button
          className={`nav-item ${activeTab === "payments" ? "active" : ""}`}
          onClick={() => onSelectTab("payments")}
        >
          <div className="nav-item-left">
            <CreditCard size={18} />
            <span>Payment Management</span>
          </div>
        </button>
      </nav>

      {/* Footer Profile & Logout */}
      <div className="sidebar-footer">
        <div className="staff-pill">
          <div className="staff-avatar">
            {staffUser?.display_name?.charAt(0) || "A"}
          </div>
          <div className="staff-info">
            <div className="staff-name">
              {staffUser?.display_name || "Super Admin"}
            </div>
            <div className="staff-role">TechMasters Admin</div>
          </div>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={onLogout}
          title="Sign Out of Admin Console"
          style={{ padding: "0.4rem", borderRadius: "var(--radius-sm)", color: "#FFFFFF", background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)" }}
        >
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
};
