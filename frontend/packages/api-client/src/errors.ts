/**
 * Standardized API Error Handling for Bagodi Platform.
 * Exports Error Class Hierarchy and Structured Error Extractor.
 */

export class ApiError extends Error {
  public statusCode: number;
  public details?: unknown;
  public errorCode?: string;

  constructor(message: string, statusCode: number = 500, details?: unknown, errorCode?: string) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.details = details;
    this.errorCode = errorCode;
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  get error(): string {
    return this.errorCode || "API_ERROR";
  }

  get status(): number {
    return this.statusCode;
  }
}

export class AuthenticationError extends ApiError {
  constructor(message: string = "Authentication required or token expired", details?: unknown) {
    super(message, 401, details, "UNAUTHORIZED");
    this.name = "AuthenticationError";
    Object.setPrototypeOf(this, AuthenticationError.prototype);
  }
}

export class ForbiddenError extends ApiError {
  constructor(message: string = "Access denied: insufficient permissions", details?: unknown) {
    super(message, 403, details, "FORBIDDEN");
    this.name = "ForbiddenError";
    Object.setPrototypeOf(this, ForbiddenError.prototype);
  }
}

export class NotFoundError extends ApiError {
  constructor(message: string = "Requested resource not found", details?: unknown) {
    super(message, 404, details, "NOT_FOUND");
    this.name = "NotFoundError";
    Object.setPrototypeOf(this, NotFoundError.prototype);
  }
}

export class ValidationError extends ApiError {
  public errors?: Record<string, string[]>;

  constructor(message: string = "Validation failed", errors?: Record<string, string[]>, details?: unknown) {
    super(message, 422, details, "VALIDATION_ERROR");
    this.name = "ValidationError";
    this.errors = errors;
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

export class ServerError extends ApiError {
  constructor(message: string = "Internal server error occurred", details?: unknown) {
    super(message, 500, details, "SERVER_ERROR");
    this.name = "ServerError";
    Object.setPrototypeOf(this, ServerError.prototype);
  }
}

export class NetworkError extends ApiError {
  constructor(message: string = "Network connection failed", details?: unknown) {
    super(message, 0, details, "NETWORK_ERROR");
    this.name = "NetworkError";
    Object.setPrototypeOf(this, NetworkError.prototype);
  }
}

export interface ExtractedApiError {
  error: string;
  message: string;
  details?: Record<string, unknown>;
  status?: number;
}

export function extractApiError(err: unknown, status?: number): ExtractedApiError {
  if (!err || typeof err !== "object") {
    if (status === 401) {
      return { error: "UNAUTHORIZED", message: "Session expired or invalid. Please log in again.", status: 401 };
    }
    if (status === 403) {
      return { error: "FORBIDDEN", message: "You do not have permission to perform this action.", status: 403 };
    }
    if (status === 404) {
      return { error: "NOT_FOUND", message: "The requested resource was not found.", status: 404 };
    }
    return {
      error: "UNKNOWN_ERROR",
      message: typeof err === "string" ? err : "An unexpected error occurred. Please try again.",
      status,
    };
  }

  const record = err as Record<string, unknown>;

  // 1. Canonical error format: { error: string, message: string, details?: object }
  if (typeof record.error === "string" && typeof record.message === "string") {
    return {
      error: record.error,
      message: record.message,
      details: typeof record.details === "object" && record.details !== null
        ? (record.details as Record<string, unknown>)
        : undefined,
      status,
    };
  }

  // 2. FastAPI validation error format: { detail: [ { loc, msg, type } ] }
  if (Array.isArray(record.detail)) {
    const messages = record.detail
      .map((item: unknown) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          const locArr = (item as { loc?: unknown[] }).loc;
          const loc = Array.isArray(locArr)
            ? locArr.filter((l: unknown) => l !== "body").map(String).join(".")
            : "";
          const msg = String((item as { msg?: unknown }).msg || "");
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .filter(Boolean);

    return {
      error: "VALIDATION_ERROR",
      message: messages.join("; ") || "Invalid request payload.",
      details: { rawErrors: record.detail },
      status,
    };
  }

  // 3. FastAPI simple detail format: { detail: string }
  if (typeof record.detail === "string") {
    return {
      error: "HTTP_ERROR",
      message: record.detail,
      status,
    };
  }

  // 4. Standard Error object: new Error(message)
  if (typeof record.message === "string") {
    return {
      error: (record.errorCode as string) || (record.error as string) || "CLIENT_ERROR",
      message: record.message,
      status: (record.statusCode as number) || status,
    };
  }

  // Fallbacks by HTTP status code
  if (status === 401) {
    return { error: "UNAUTHORIZED", message: "Session expired or invalid. Please log in again.", status: 401 };
  }
  if (status === 403) {
    return { error: "FORBIDDEN", message: "You do not have permission to perform this action.", status: 403 };
  }
  if (status === 404) {
    return { error: "NOT_FOUND", message: "The requested resource was not found.", status: 404 };
  }
  if (status === 409) {
    return { error: "CONFLICT", message: "Resource conflict or inventory unavailable.", status: 409 };
  }
  if (status && status >= 500) {
    return { error: "SERVER_ERROR", message: "Backend service error. Please try again later.", status };
  }

  return {
    error: "UNKNOWN_ERROR",
    message: "An unexpected error occurred.",
    status,
  };
}

export function formatErrorMessage(err: unknown): string {
  return extractApiError(err).message;
}
