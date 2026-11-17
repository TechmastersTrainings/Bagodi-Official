import React from "react";
import {
  LayoutDashboard,
  Users,
  Shirt,
  ShoppingBag,
  RotateCcw,
  Truck,
  Boxes,
  Tag,
  PackagePlus,
  Store,
  BarChart3,
  LogOut,
  MapPin,
} from "lucide-react";
import type { StaffUser, PhysicalStore } from "../types";

export type NavTab =
  | "dashboard"
  | "users"
  | "catalog"
  | "orders"
  | "returns"
  | "delivery"
  | "coupons"
  | "inventory"
  | "procurement"
  | "stores"
  | "analytics";

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  staffUser: StaffUser;
  activeStore: PhysicalStore | null;
  onLogout: () => void;
  pendingOrdersCount?: number;
  pendingReturnsCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  staffUser,
  activeStore,
  onLogout,
  pendingOrdersCount = 0,
  pendingReturnsCount = 0,
}) => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-title">
          <span>Bagodi</span>
          <span className="brand-badge">Merchant</span>
        </div>
        <div className="store-selector-pill">
          <div className="location">
            <MapPin size={14} color="var(--brand-terracotta)" />
            <span>{activeStore?.name || "Bidar Flagship"}</span>
          </div>
          <div className="dot" title="Store Online & Active" />
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Merchant Core Modules</div>

        <button
          className={`nav-item ${currentTab === "dashboard" ? "active" : ""}`}
          onClick={() => onTabChange("dashboard")}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </button>

        <button
          className={`nav-item ${currentTab === "users" ? "active" : ""}`}
          onClick={() => onTabChange("users")}
        >
          <Users size={18} />
          <span>User Management</span>
        </button>

        <button
          className={`nav-item ${currentTab === "catalog" ? "active" : ""}`}
          onClick={() => onTabChange("catalog")}
        >
          <Shirt size={18} />
          <span>Product Management</span>
        </button>

        <button
          className={`nav-item ${currentTab === "orders" ? "active" : ""}`}
          onClick={() => onTabChange("orders")}
        >
          <ShoppingBag size={18} />
          <span>Order Management</span>
          {pendingOrdersCount > 0 && (
            <span className="badge">{pendingOrdersCount}</span>
          )}
        </button>

        <button
          className={`nav-item ${currentTab === "returns" ? "active" : ""}`}
          onClick={() => onTabChange("returns")}
        >
          <RotateCcw size={18} />
          <span>Return / Exchange</span>
          {pendingReturnsCount > 0 && (
            <span className="badge">{pendingReturnsCount}</span>
          )}
        </button>

        <button
          className={`nav-item ${currentTab === "delivery" ? "active" : ""}`}
          onClick={() => onTabChange("delivery")}
        >
          <Truck size={18} />
          <span>Delivery Management</span>
        </button>

        <div className="nav-section-label">Store Operations</div>

        <button
          className={`nav-item ${currentTab === "inventory" ? "active" : ""}`}
          onClick={() => onTabChange("inventory")}
        >
          <Boxes size={18} />
          <span>Stock & Ledger</span>
        </button>

        <button
          className={`nav-item ${currentTab === "coupons" ? "active" : ""}`}
          onClick={() => onTabChange("coupons")}
        >
          <Tag size={18} />
          <span>Discounts & Coupons</span>
        </button>

        <button
          className={`nav-item ${currentTab === "stores" ? "active" : ""}`}
          onClick={() => onTabChange("stores")}
        >
          <Store size={18} />
          <span>Store Branches</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <div className="staff-info">
          <div className="staff-avatar">
            {staffUser.display_name?.charAt(0) || "B"}
          </div>
          <div>
            <div className="staff-name">
              {staffUser.display_name || "Staff Member"}
            </div>
            <div className="staff-role">{staffUser.role.replace("_", " ")}</div>
          </div>
        </div>
        <button
          className="btn btn-sm"
          onClick={onLogout}
          title="Sign Out"
          style={{
            padding: "0.45rem",
            borderRadius: "var(--radius-sm)",
            background: "rgba(255, 255, 255, 0.1)",
            border: "1px solid rgba(255, 255, 255, 0.18)",
            color: "#FFFFFF",
            cursor: "pointer",
          }}
        >
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
};

