const API_ROOT = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api`;
export const JSON_UPLOAD_LIMIT = 4 * 1024 * 1024;
export const DEFAULT_TIMEOUT_MS = 60 * 1000;
export const IMPORT_TIMEOUT_MS = 180 * 1000;

export { API_ROOT };

function isAbortError(error) {
  return error?.name === "AbortError" || error?.name === "TimeoutError";
}

export async function request(url, options = {}) {
  const { timeout = DEFAULT_TIMEOUT_MS, signal: outerSignal, ...rest } = options;
  const controller = new AbortController();
  const timer = timeout
    ? setTimeout(() => controller.abort("timeout"), timeout)
    : null;
  if (outerSignal) {
    if (outerSignal.aborted) {
      controller.abort(outerSignal.reason);
    } else {
      outerSignal.addEventListener("abort", () => controller.abort(outerSignal.reason), { once: true });
    }
  }
  try {
    const response = await fetch(url, { ...rest, signal: controller.signal });
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/octet-stream") || contentType.includes("officedocument")) {
      if (!response.ok) {
        throw new Error(`Download failed (HTTP ${response.status}).`);
      }
      return response;
    }
    const text = await response.text();
    let payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(
        text?.trim()
          ? `Request failed (HTTP ${response.status}). ${text.replace(/<[^>]+>/g, " ").trim().slice(0, 180)}`
          : `Invalid response (HTTP ${response.status}).`
      );
    }
    if (!response.ok) {
      const detail = payload.errors
        ?.slice(0, 5)
        .map((error) => `Row ${error.row}: ${error.message}`)
        .join("; ");
      throw new Error(
        detail ? `${payload.message} ${detail}` : payload.message || `HTTP ${response.status}`
      );
    }
    return payload;
  } catch (error) {
    if (isAbortError(error) || controller.signal.aborted) {
      const cancelled = Boolean(outerSignal?.aborted);
      const next = new Error(cancelled ? "Request cancelled." : "Request timed out.");
      next.name = cancelled ? "AbortError" : "TimeoutError";
      throw next;
    }
    throw error;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new Error("Could not read the file."));
    reader.readAsDataURL(file);
  });
}
