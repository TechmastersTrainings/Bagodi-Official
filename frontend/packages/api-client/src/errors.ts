/**
 * Standardized API Error Handling for Bagodi Platform.
 * Extracts structured server error codes, messages, and validation errors.
 */

export interface ApiError {
  error: string;
  message: string;
  details?: Record<string, unknown>;
  status?: number;
}

export function extractApiError(err: unknown, status?: number): ApiError {
  if (!err || typeof err !== "object") {
    return {
      error: "UNKNOWN_ERROR",
      message: typeof err === "string" ? err : "An unexpected error occurred. Please try again.",
      status,
    };
  }

  const record = err as Record<string, unknown>;

  // 1. Bagodi Platform canonical error format: { error: string, message: string, details?: object }
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
          const itemRecord = item as Record<string, unknown>;
          const locArr = Array.isArray(itemRecord.loc) ? (itemRecord.loc as unknown[]) : [];
          const loc = locArr.filter((l) => l !== "body").map(String).join(".");
          const msg = String(itemRecord.msg);
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
      error: "CLIENT_ERROR",
      message: record.message,
      status,
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
