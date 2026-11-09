"""Plain-text PDF for the current MALSTAR Ops view. Uses the built-in Helvetica face."""


def _pdf_text(value):
    cleaned = []
    for char in str(value or ""):
        code = ord(char)
        if char in "()\\":
            cleaned.append("\\" + char)
        elif 32 <= code < 127:
            cleaned.append(char)
        else:
            cleaned.append("?")
    return "".join(cleaned)


def _wrap(text, width):
    words = str(text or "").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if len(trial) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _cohort_line(label, cohort):
    cohort = cohort or {}
    return (
        f"{label}: {cohort.get('total', 0)} bookings, {cohort.get('converted', 0)} converted "
        f"({cohort.get('conversionRate', 0)}%), {cohort.get('processing', 0)} processing, "
        f"{cohort.get('missingShipment', 0)} missing shipment, "
        f"process {cohort.get('avgProcessLabel', '—')}, wait {cohort.get('avgWaitLabel', '—')}."
    )


def report_lines(payload):
    payload = payload or {}
    meta = payload.get("meta") or {}
    compare = payload.get("compare") or {}
    start = meta.get("dateFrom") or ""
    end = meta.get("dateTo") or ""
    period = start if start == end else f"{start} to {end}"
    lines = [
        ("title", "MALSTAR Ops"),
        ("meta", period or "Selected dates"),
        ("meta", meta.get("filename") or ""),
        ("blank", ""),
        ("head", "Overview"),
        ("body", _cohort_line("GSC", compare.get("gsc"))),
        ("body", _cohort_line("Area", compare.get("area"))),
    ]
    for item in payload.get("conclusions") or []:
        if item.get("kind") == "overview":
            continue
        lines.append(("blank", ""))
        lines.append(("head", item.get("section") or item.get("kind") or "Section"))
        if item.get("lead"):
            lines.append(("body", item.get("lead")))
        if item.get("text"):
            lines.append(("body", item.get("text")))
    handlers = payload.get("series", {}).get("byHandler") or []
    if handlers:
        lines.append(("blank", ""))
        lines.append(("head", "Roster volume"))
        for item in handlers[:10]:
            label = str(item.get("label") or "").split("@", 1)[0]
            lines.append(("body", f"{label}: {item.get('count', 0)}"))
    return [item for item in lines if item[0] == "blank" or str(item[1]).strip()]


def build_ops_pdf(payload):
    wrapped = []
    for kind, text in report_lines(payload):
        if kind == "blank":
            wrapped.append(("blank", ""))
            continue
        width = 78 if kind == "body" else 64
        for line in _wrap(text, width):
            wrapped.append((kind, line))

    pages = []
    cursor = []
    used = 0
    limit = 46
    for item in wrapped:
        cursor.append(item)
        used += 1
        if used >= limit:
            pages.append(cursor)
            cursor = []
            used = 0
    if cursor or not pages:
        pages.append(cursor)

    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids = []
    content_ids = []
    for page in pages:
        commands = ["BT", "/F2 16 Tf", "50 800 Td", "16 TL"]
        first = True
        for kind, line in page:
            if not first:
                commands.append("T*")
            first = False
            if kind == "title":
                commands.append("/F2 16 Tf")
            elif kind == "head":
                commands.append("/F2 12 Tf")
            else:
                commands.append("/F1 10 Tf")
            commands.append(f"({_pdf_text(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        content_ids.append(add(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        ))
        page_ids.append(None)

    pages_id_placeholder = len(objects) + 1 + len(page_ids)
    for index, content_id in enumerate(content_ids):
        page_ids[index] = add(
            "<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 595 842] "
            "/Resources << /Font << /F1 {font} 0 R /F2 {bold} 0 R >> >> "
            "/Contents {content} 0 R >>".format(
                pages=pages_id_placeholder,
                font=font_id,
                bold=bold_id,
                content=content_id,
            )
        )
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add(f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>")
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body if isinstance(body, bytes) else body.encode("latin-1", "replace"))
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(output)
