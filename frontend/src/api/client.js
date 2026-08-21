const API_ROOT = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api`;
export const JSON_UPLOAD_LIMIT = 4 * 1024 * 1024;

export { API_ROOT };

export async function request(url, options = {}) {
  const response = await fetch(url, options);
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
