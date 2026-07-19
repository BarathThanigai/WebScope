export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export function formatApiError(data) {
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${item.loc?.slice(1).join(".") || "field"}: ${item.msg}`)
      .join(" ");
  }
  if (typeof detail === "string") return detail;
  return detail?.message || "The API request failed.";
}

export async function apiRequest(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data));
  }
  return data;
}
