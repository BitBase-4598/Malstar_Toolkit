import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

const MARGIN = 36;

function conclusionBlocks(root) {
  const blocks = [];
  for (const item of root.querySelectorAll(".dash-conclusions > li")) {
    if (item.classList.contains("dash-conclusion-group")) {
      const period = item.querySelector(".dash-conclusion-period")?.textContent?.trim() || "";
      blocks.push({ title: "Handlers", period, body: "" });
      for (const child of item.querySelectorAll(":scope > ul > li")) {
        const body = [...child.querySelectorAll("p")].map((node) => node.textContent.trim()).filter(Boolean).join(" ");
        blocks.push({
          title: child.querySelector("strong")?.textContent?.trim() || "",
          period: "",
          body,
        });
      }
      continue;
    }
    blocks.push({
      title: item.querySelector(".dash-conclusion-section")?.textContent?.trim() || "",
      period: item.querySelector(".dash-conclusion-period")?.textContent?.trim() || "",
      body: [...item.querySelectorAll("p")].map((node) => node.textContent.trim()).filter(Boolean).join(" "),
    });
  }
  return blocks;
}

function ensureSpace(pdf, y, needed) {
  const pageHeight = pdf.internal.pageSize.getHeight();
  if (y + needed <= pageHeight - MARGIN) {
    return y;
  }
  pdf.addPage();
  return MARGIN;
}

function writeLine(pdf, text, y, { size = 11, bold = false, color = [20, 20, 20] } = {}) {
  const pageWidth = pdf.internal.pageSize.getWidth();
  pdf.setFont("helvetica", bold ? "bold" : "normal");
  pdf.setFontSize(size);
  pdf.setTextColor(...color);
  const lines = pdf.splitTextToSize(text, pageWidth - MARGIN * 2);
  const lineHeight = size + 4;
  let cursor = y;
  for (const line of lines) {
    cursor = ensureSpace(pdf, cursor, lineHeight);
    pdf.text(line, MARGIN, cursor);
    cursor += lineHeight;
  }
  return cursor;
}

function skipColorFunction(css, start) {
  let depth = 0;
  for (let index = start; index < css.length; index += 1) {
    const char = css[index];
    if (char === "(") {
      depth += 1;
    } else if (char === ")") {
      depth -= 1;
      if (depth === 0) {
        return index + 1;
      }
    }
  }
  return css.length;
}

function replaceColorFunctions(css) {
  const names = ["color-mix", "color", "oklch", "oklab", "lch", "lab"];
  let output = "";
  let index = 0;
  while (index < css.length) {
    let found = null;
    for (const name of names) {
      const at = css.indexOf(`${name}(`, index);
      if (at !== -1 && (found === null || at < found.at)) {
        found = { name, at };
      }
    }
    if (!found) {
      output += css.slice(index);
      break;
    }
    const prefix = css.slice(Math.max(0, found.at - 1), found.at);
    if (prefix && /[\w-]/.test(prefix)) {
      output += css.slice(index, found.at + found.name.length);
      index = found.at + found.name.length;
      continue;
    }
    output += css.slice(index, found.at);
    output += "#d4d4d4";
    index = skipColorFunction(css, found.at + found.name.length);
  }
  return output;
}

function sanitizeClone(doc) {
  for (const style of doc.querySelectorAll("style")) {
    const text = (style.textContent || "").replace(/@font-face\s*\{[^}]*\}/g, "");
    style.textContent = replaceColorFunctions(text);
  }
}

async function chartImage(node) {
  const canvas = await html2canvas(node, {
    scale: 2,
    backgroundColor: "#ffffff",
    useCORS: true,
    logging: false,
    onclone: (doc) => sanitizeClone(doc),
  });
  return canvas;
}

export async function exportOpsPdf(root, filename) {
  if (!root) {
    throw new Error("The Ops page is not ready to export.");
  }
  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  let y = MARGIN;

  y = writeLine(pdf, "MALSTAR Ops", y, { size: 18, bold: true, color: [0, 36, 61] });
  y += 6;

  for (const block of conclusionBlocks(root)) {
    if (block.title) {
      y = writeLine(pdf, block.title, y + 8, { size: 13, bold: true, color: [0, 36, 61] });
    }
    if (block.period) {
      y = writeLine(pdf, block.period, y, { size: 10, color: [0, 90, 140] });
    }
    if (block.body) {
      y = writeLine(pdf, block.body, y, { size: 11 });
    }
  }

  const charts = [
    root.querySelector(".dash-compare"),
    ...root.querySelectorAll(".dash-charts > .card"),
  ].filter(Boolean);

  for (const node of charts) {
    const canvas = await chartImage(node);
    const maxWidth = pageWidth - MARGIN * 2;
    let drawWidth = maxWidth;
    let drawHeight = (canvas.height * drawWidth) / canvas.width;
    const maxHeight = pageHeight - MARGIN * 2;
    if (drawHeight > maxHeight) {
      drawHeight = maxHeight;
      drawWidth = (canvas.width * drawHeight) / canvas.height;
    }
    y = ensureSpace(pdf, y + 14, drawHeight);
    pdf.addImage(canvas.toDataURL("image/png"), "PNG", MARGIN, y, drawWidth, drawHeight);
    y += drawHeight;
  }

  pdf.save(filename || "malstar-ops.pdf");
}
