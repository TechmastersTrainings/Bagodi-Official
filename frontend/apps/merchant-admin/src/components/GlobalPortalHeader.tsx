import React from "react";
import { ExternalLink, Store } from "lucide-react";

interface GlobalPortalHeaderProps {
  currentPath?: string;
  onNavigate?: (path: string) => void;
  userRole?: string | null;
  userName?: string | null;
  onSignOut?: () => void;
}

export const GlobalPortalHeader: React.FC<GlobalPortalHeaderProps> = ({
  userRole,
  userName,
  onSignOut,
}) => {
  return (
    <header className="global-portal-bar">
      <div className="global-portal-left">
        <span className="global-portal-brand">BAGODI</span>
        <span className="global-portal-sep">|</span>
        <span className="global-portal-subtitle">Merchant Operations Portal</span>
      </div>

      <nav className="global-portal-nav" aria-label="Portal Navigation">
        <a
          href="http://localhost:5174"
          target="_blank"
          rel="noopener noreferrer"
          className="portal-nav-btn"
          title="Open live customer shopping experience in new tab"
        >
          <span>View Customer Storefront</span>
          <ExternalLink size={13} />
        </a>
      </nav>

      <div className="global-portal-right">
        {userName ? (
          <div className="portal-user-badge">
            <span className="user-label">
              {userName} {userRole ? `(${userRole.replace(/_/g, " ")})` : ""}
            </span>
            {onSignOut && (
              <button type="button" className="portal-signout-btn" onClick={onSignOut}>
                Sign Out
              </button>
            )}
          </div>
        ) : (
          <span className="portal-status-indicator">● Store Active</span>
        )}
      </div>
    </header>
  );
};
