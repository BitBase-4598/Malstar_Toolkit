export const STATUSES = [
  { id: "pending_review", label: "Pending review" },
  { id: "reviewed", label: "Reviewed" },
  { id: "closed", label: "Closed" },
];

export const FILE_ACCEPT =
  ".docx,.xlsx,.png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif";

export const DETAIL_FIELDS = [
  ["hbl", "HBL"],
  ["name", "Name"],
  ["wronglyIdentified", "Wrongly identified"],
  ["incorrect", "Incorrect"],
  ["corrected", "Corrected"],
  ["causeOfError", "Cause of error"],
  ["adjustedHbl", "Adjusted HBL"],
  ["gscPic", "GSC PIC"],
  ["week", "Week"],
  ["date", "Date"],
  ["action", "Action"],
];

export const CASE_MAILBOXES = [
  "CUSLCL.SZH@LnS.maersk.com",
  "CUSLCLLEUR.SZH@LnS.maersk.com",
  "HKGLCL@LnS.maersk.com",
  "TWNLCL-CUS@LnS.maersk.com",
];

export const emptyForm = {
  bookingOrderId: "",
  shipmentNumber: "",
  email: "",
  description: "",
  status: "pending_review",
};

export const IDENTIFIER_REQUIRED = "Booking order ID or shipment number is required.";

export function statusLabel(value) {
  return STATUSES.find((item) => item.id === value)?.label || value || "—";
}

export function splitEmails(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function joinEmails(values) {
  return (values || []).map((item) => String(item || "").trim()).filter(Boolean).join(", ");
}

export function emailLabel(value) {
  const items = splitEmails(value);
  return items.length ? items.join(", ") : "All";
}

export function mailboxOptions(value) {
  const extras = splitEmails(value).filter((item) => !CASE_MAILBOXES.includes(item));
  return [...CASE_MAILBOXES, ...extras].map((item) => ({ value: item, label: item }));
}

export function displayDate(row) {
  const raw = row.date || row.startTime || row.createdAt || "";
  return raw.slice(0, 10) || "—";
}

export function screenshotFile(blob) {
  const type = blob.type || "image/png";
  const subtype = (type.split("/")[1] || "png").split("+")[0];
  const ext = subtype === "jpeg" ? "jpg" : subtype;
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const given = blob.name && !/^image\./i.test(blob.name) ? blob.name : "";
  return new File([blob], given || `screenshot-${stamp}.${ext}`, { type });
}

export function imagesFromClipboard(event) {
  const items = Array.from(event.clipboardData?.items || []);
  const files = [];
  for (const item of items) {
    if (item.kind === "file" && String(item.type || "").startsWith("image/")) {
      const blob = item.getAsFile();
      if (blob) {
        files.push(screenshotFile(blob));
      }
    }
  }
  return files;
}
