export function lettersOnly(value) {
  return (value || "").normalize("NFKC").replace(/\P{L}+/gu, "");
}
