/**
 * Secure Token Storage Adapter
 * Provides platform-aware storage (Web LocalStorage/SessionStorage & Capacitor Native)
 */

export interface TokenStorageStrategy {
  getAccessToken(): Promise<string | null> | string | null;
  setAccessToken(token: string): Promise<void> | void;
  getRefreshToken(): Promise<string | null> | string | null;
  setRefreshToken(token: string): Promise<void> | void;
  clearTokens(): Promise<void> | void;
}

class HybridPlatformTokenStorage implements TokenStorageStrategy {
  private inMemoryAccessToken: string | null = null;
  private readonly REFRESH_KEY = "bagodi_auth_rt";
  private readonly ACCESS_KEY = "bagodi_auth_at";

  getAccessToken(): string | null {
    if (this.inMemoryAccessToken) return this.inMemoryAccessToken;
    try {
      if (typeof window !== "undefined") {
        return localStorage.getItem(this.ACCESS_KEY) || localStorage.getItem("bagodi_access_token");
      }
    } catch {
      // Storage restricted
    }
    return null;
  }

  setAccessToken(token: string): void {
    this.inMemoryAccessToken = token;
    try {
      if (typeof window !== "undefined") {
        localStorage.setItem(this.ACCESS_KEY, token);
        localStorage.setItem("bagodi_access_token", token);
      }
    } catch {
      // Storage restricted
    }
  }

  getRefreshToken(): string | null {
    try {
      if (typeof window !== "undefined") {
        return (
          localStorage.getItem(this.REFRESH_KEY) ||
          sessionStorage.getItem(this.REFRESH_KEY) ||
          localStorage.getItem("bagodi_refresh_token")
        );
      }
    } catch {
      // Storage restricted
    }
    return null;
  }

  setRefreshToken(token: string): void {
    try {
      if (typeof window !== "undefined") {
        localStorage.setItem(this.REFRESH_KEY, token);
        sessionStorage.setItem(this.REFRESH_KEY, token);
        localStorage.setItem("bagodi_refresh_token", token);
      }
    } catch {
      // Storage restricted
    }
  }

  clearTokens(): void {
    this.inMemoryAccessToken = null;
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem(this.ACCESS_KEY);
        localStorage.removeItem(this.REFRESH_KEY);
        localStorage.removeItem("bagodi_access_token");
        localStorage.removeItem("bagodi_refresh_token");
        sessionStorage.removeItem(this.REFRESH_KEY);
      }
    } catch {
      // Storage restricted
    }
  }
}

export const tokenStorage = new HybridPlatformTokenStorage();
