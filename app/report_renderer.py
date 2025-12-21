from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")



def _report_id(snapshot: Dict[str, Any]) -> str:
    try:
        raw = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
    except Exception:
        raw = repr(snapshot).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:10]


def render_report_html(
    snapshot: Dict[str, Any],
    *,
    templates_dir: str | Path = "templates",
    css_path: str = "static/report.css",
    include_baseline_crypto_risks: bool | None = None,
) -> str:
    """Render snapshot to HTML using Jinja2."""
    templates_dir = str(templates_dir)
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("report.html")

    fact = snapshot.get("token_fact_sheet") or {}
    asset = (fact.get("asset") or {})
    classification = (fact.get("classification") or {})

    risk_dashboard = snapshot.get("risk_dashboard") or {}
    overall = (risk_dashboard.get("overall_band") or classification.get("overall_band") or {})

    exec_summary = snapshot.get("executive_summary") or {}

    report_profile = (os.getenv("REPORT_PROFILE") or "").strip().lower()  # e.g. "global" / "uk"
    if include_baseline_crypto_risks is None:
        if report_profile == "uk":
            include_baseline_crypto_risks = True
        else:
            include_baseline_crypto_risks = os.getenv("INCLUDE_BASELINE_CRYPTO_RISKS", "0") == "1"


    # UK-style generic risk block (baseline) bullets
    baseline_general_risks = []
    baseline_general_heading = "Cryptoasset risks — general (baseline)"
    baseline_general_explainer = (
        "This section lists generic cryptoasset risk statements that some regulators expect to appear on listing pages "
        "or consumer-facing communications. Use it as a checklist when drafting listing-page risk warnings and "
        "promotional disclosures; omit it where not required for the intended jurisdiction."
    )
    try:
        from .asset_risks_baseline import BASELINE_BULLETS
        baseline_general_risks = [
            b.text for b in BASELINE_BULLETS if getattr(b, "group", None) == "baseline_crypto"
        ]
    except Exception:
        baseline_general_risks = []

    category_intros = {
        "DeFi risks": "These risks are relevant where the token is linked to decentralised finance protocols and smart contracts.",
        "Stablecoin risks": "These risks apply where the token is used or marketed as a stable-value asset or stablecoin.",
        "Wrapped token risks": "These risks apply where exposure depends on bridges, custodians, or wrapping mechanics.",
        "Memecoin risks": "These risks apply where price discovery and demand depend heavily on sentiment, virality, and promotional dynamics.",
        "Security token risks": "These risks apply where the token may exhibit securities-like characteristics or depends on issuer performance and disclosures.",
        "Governance & utility token risks": "These risks apply where the token’s function is governance rights, protocol control, or utility within an ecosystem.",
        "Cryptoasset risks (baseline)": "Generic cryptoasset risks that may be required for some retail contexts; may be omitted for global reports unless selected.",
    }

    ctx = {
        "snapshot": snapshot,
        "generated_at": _utc_now_str(),
        "report_id": _report_id(snapshot),
        "css_path": css_path,
        "asset": asset,
        "classification": classification,
        "overall": overall,
        "posture": classification.get("posture"),
        "escalations_count": classification.get("board_escalations_count") or len(snapshot.get("board_escalations") or []),
        "exec": exec_summary,
        "include_baseline_crypto_risks": bool(include_baseline_crypto_risks),
        "category_intros": category_intros,
        "baseline_general_heading": baseline_general_heading,
        "baseline_general_explainer": baseline_general_explainer,
        "baseline_general_risks": baseline_general_risks,
    }

    return template.render(**ctx)


def write_report_html(
    snapshot: Dict[str, Any],
    *,
    out_path: str | Path,
    templates_dir: str | Path = "templates",
    static_dir: str | Path = "static",
) -> Path:
    out_path = Path(out_path)
    static_dir = Path(static_dir)
    css_file = static_dir / "report.css"
    css_path = os.path.relpath(css_file.as_posix(), start=out_path.parent.as_posix())
    html = render_report_html(snapshot, templates_dir=templates_dir, css_path=css_path)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def write_report_pdf(snapshot: Dict[str, Any], *, out_path: str | Path) -> Path:
    """Write a PDF report using ReportLab.

    This PDF prioritises clean, printable committee readability (cards, chips, clear hierarchy).
    """
    import io
    import urllib.request

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
        Flowable,
        Image,
    )


    out_path = Path(out_path)

    # -----------------------------
    # Helpers
    # -----------------------------
    def _pdf_text(v: Any) -> str:
        """Normalise text so it renders reliably with built-in PDF fonts (Helvetica)."""
        if v is None:
            return ""
        s = str(v)

        # Common unicode punctuation / hyphens that Helvetica (WinAnsi) won't render consistently
        replacements = {
            "\u2010": "-",  # hyphen
            "\u2011": "-",  # non-breaking hyphen
            "\u2012": "-",  # figure dash
            "\u2013": "-",  # en dash
            "\u2014": "-",  # em dash
            "\u2212": "-",  # minus
            "\u00a0": " ",  # nbsp
            "\u2009": " ",  # thin space
            "\u2018": "'", "\u2019": "'",  # smart single quotes
            "\u201c": '"', "\u201d": '"',  # smart double quotes
        }
        for a, b in replacements.items():
            s = s.replace(a, b)
        return s

    def _fmt_num(v: Any, nd: int = 3) -> str:
        try:
            if v is None or v == "":
                return ""
            return f"{float(v):.{nd}f}"
        except Exception:
            return _pdf_text(v)

    def _soft_wrap_url(u: Any) -> str:
        s = _pdf_text(u)
        if not s:
            return ""
        # Insert line breaks after slashes so long URLs don't run off the page.
        parts = s.split("/")
        return "/<br/>".join(parts)

    def _headline_stats_text(stats: Any) -> str:
        try:
            items = list(stats or [])
        except Exception:
            items = []
        if not items:
            return "—"
        parts = []
        for it in items[:6]:
            if not isinstance(it, dict):
                continue
            lbl = str(it.get("label") or "").strip()
            val = str(it.get("value") or "").strip()
            if not lbl or not val:
                continue
            parts.append(f"{lbl}: {val}")
        return " • ".join(parts) if parts else "—"


    def _utc_now_str() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _band_color(n: int) -> colors.Color:
        if n <= 1:
            return colors.HexColor("#a7c7ff")
        if n == 2:
            return colors.HexColor("#8ee6c8")
        if n == 3:
            return colors.HexColor("#ffd08a")
        if n == 4:
            return colors.HexColor("#ffad73")
        return colors.HexColor("#ff7a7a")

    def _staleness_color(label: str | None) -> colors.Color:
        s = (label or "").lower()
        if "critical" in s:
            return colors.HexColor("#ff7a7a")
        if "warning" in s or "fast" in s:
            return colors.HexColor("#ffad73")
        if "slow" in s:
            return colors.HexColor("#ffd08a")
        return colors.HexColor("#c9ced8")

    class Card(Flowable):
        def __init__(
            self,
            content: list,
            *,
            bg: colors.Color = colors.white,
            stroke: colors.Color = colors.HexColor("#e6e8ee"),
            left_bar: colors.Color | None = None,
            radius: float = 10,
            pad: float = 7,
            gap: float = 4,
        ):
            super().__init__()
            self._content = content
            self._bg = bg
            self._stroke = stroke
            self._left_bar = left_bar
            self._radius = radius
            self._pad = pad
            self._gap = gap
            self.width = 0
            self.height = 0

        def wrap(self, availWidth, availHeight):
            self.width = availWidth
            inner_w = max(10, availWidth - 2 * self._pad)
            total_h = self._pad
            for i, f in enumerate(self._content):
                w, h = f.wrap(inner_w, availHeight)
                total_h += h
                if i < len(self._content) - 1:
                    total_h += self._gap
            total_h += self._pad
            self.height = total_h
            return availWidth, total_h

        def draw(self):
            c = self.canv
            c.saveState()

            # Card background
            c.setFillColor(self._bg)
            c.setStrokeColor(self._stroke)
            c.setLineWidth(0.8)
            c.roundRect(0, 0, self.width, self.height, self._radius, fill=1, stroke=1)

            # Left accent bar
            if self._left_bar is not None:
                c.setFillColor(self._left_bar)
                c.rect(0, 0, 4, self.height, fill=1, stroke=0)

            # Content
            inner_w = max(10, self.width - 2 * self._pad)
            x = self._pad
            y = self.height - self._pad
            for i, f in enumerate(self._content):
                w, h = f.wrap(inner_w, y)
                y -= h
                f.drawOn(c, x, y)
                if i < len(self._content) - 1:
                    y -= self._gap

            c.restoreState()

    # -----------------------------
    # Data extraction
    # -----------------------------
    fact = snapshot.get("token_fact_sheet") or {}
    asset = fact.get("asset") or {}
    classification = fact.get("classification") or {}

    risk_dashboard = snapshot.get("risk_dashboard") or {}
    overall = risk_dashboard.get("overall_band") or classification.get("overall_band") or {}

    exec_summary = snapshot.get("executive_summary") or {}
    listing_requirements = snapshot.get("listing_requirements") or []
    asset_specific_risks = snapshot.get("asset_specific_risks") or []
    listing_ctx = snapshot.get("listing_context") or {}

    board_escalations = snapshot.get("board_escalations") or []
    esc_count = len(board_escalations)

    generated_at = _utc_now_str()
    report_id = _report_id(snapshot)

    posture = (exec_summary.get("overall_posture") or listing_ctx.get("posture") or classification.get("posture") or "").strip() or "Unknown"
    band_name = overall.get("name") or "Unknown"
    band_num = int(overall.get("numeric") or 0)

    # UK baseline risk block toggle
    report_profile = (os.getenv("REPORT_PROFILE") or "").strip().lower()
    include_baseline_crypto_risks = os.getenv("INCLUDE_BASELINE_CRYPTO_RISKS", "").strip()
    if include_baseline_crypto_risks == "":
        include_baseline_crypto_risks = (report_profile == "uk")
    else:
        include_baseline_crypto_risks = include_baseline_crypto_risks.lower() in ("1", "true", "yes", "y", "on")

    baseline_general_risks = []
    baseline_general_heading = "Cryptoasset risks — general (baseline)"
    baseline_general_explainer = (
        "This section lists generic cryptoasset risk statements that some regulators expect to appear on listing pages "
        "or consumer-facing communications. Use it as a checklist when drafting listing-page risk warnings and promotional "
        "disclosures; omit it where not required for the intended jurisdiction."
    )
    try:
        from .asset_risks_baseline import BASELINE_BULLETS
        baseline_general_risks = [b.text for b in BASELINE_BULLETS if getattr(b, "group", None) == "baseline_crypto"]
    except Exception:
        baseline_general_risks = []

    # Token logo (best-effort)
    logo_reader = None
    logo_url = asset.get("logo_url")
    logo_bytes: bytes | None = None
    if isinstance(logo_url, str) and logo_url.startswith("http"):
        try:
            req = urllib.request.Request(
                logo_url,
                headers={"User-Agent": "token-report-app/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                logo_bytes = r.read()
        except Exception:
            logo_bytes = None

# -----------------------------
    # Styles
    # -----------------------------
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#0b1220"))
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor("#0b1220"))
    H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceBefore=3, spaceAfter=3, textColor=colors.HexColor("#0b1220"))
    P = ParagraphStyle("P", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.6, leading=12.2, textColor=colors.HexColor("#0b1220"))
    Muted = ParagraphStyle("Muted", parent=P, textColor=colors.HexColor("#5b6473"))
    Small = ParagraphStyle("Small", parent=P, fontSize=8.4, leading=10.5, textColor=colors.HexColor("#5b6473"))

    # -----------------------------
    # Header/footer + background
    # -----------------------------
    def _decorate(canvas, doc):
        w, h = A4
        canvas.saveState()

        # Page background
        canvas.setFillColor(colors.HexColor("#f3f4f6"))
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Header separator
        canvas.setStrokeColor(colors.HexColor("#e6e8ee"))
        canvas.setLineWidth(0.6)
        canvas.line(16 * mm, h - 18 * mm, w - 16 * mm, h - 18 * mm)

        # Optional logo
        x0 = 16 * mm
        canvas.setFillColor(colors.HexColor("#0b1220"))
        canvas.setFont("Helvetica-Bold", 9.6)
        canvas.drawString(x0, h - 14 * mm, "Token Listing Risk Assessment")

        canvas.setFont("Helvetica", 8.3)
        canvas.drawRightString(w - 16 * mm, h - 14 * mm, f"{_pdf_text(asset.get('name',''))} ({_pdf_text(asset.get('ticker',''))})")

        canvas.setFont("Helvetica", 7.8)
        canvas.setFillColor(colors.HexColor("#5b6473"))
        canvas.drawString(16 * mm, h - 16.8 * mm, f"Generated {generated_at}")
        canvas.drawRightString(w - 16 * mm, h - 16.8 * mm, f"Report ID {report_id}")

        # Footer separator
        canvas.setStrokeColor(colors.HexColor("#e6e8ee"))
        canvas.line(16 * mm, 16 * mm, w - 16 * mm, 16 * mm)
        canvas.setFont("Helvetica", 7.8)
        canvas.setFillColor(colors.HexColor("#5b6473"))
        canvas.drawString(16 * mm, 11.2 * mm, "Confidential — for internal use only")
        canvas.drawRightString(w - 16 * mm, 11.2 * mm, f"{_pdf_text(asset.get('ticker',''))} · {report_id}")

        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=f"{asset.get('name','')} ({asset.get('ticker','')}) — Token Listing Risk Assessment",
        author="Token Risk Engine",
    )

    story = []

    # -----------------------------
    # Cover / Executive summary
    # -----------------------------
    story.append(Paragraph("Token Listing Risk Assessment", H1))

    token_line = Paragraph(
        f"{_pdf_text(asset.get('name',''))} ({_pdf_text(asset.get('ticker',''))})",
        Muted,
    )

    if logo_bytes is not None:
        try:
            # Use the same reader we already downloaded; render at a fixed size
            logo_img = Image(io.BytesIO(logo_bytes), width=12 * mm, height=12 * mm)
            logo_img.hAlign = "LEFT"

            header_tbl = Table(
                [[logo_img, token_line]],
                colWidths=[14 * mm, 160 * mm],
            )
            header_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(header_tbl)
        except Exception:
            story.append(token_line)
    else:
        story.append(token_line)

    story.append(Spacer(1, 10))


    cover_rows = [
        ["Overall band", f"{band_name} ({band_num}/5)" if band_num else band_name],
        ["Posture", posture],
        ["Listing committee escalations", str(esc_count)],
        ["Token type", _pdf_text(asset.get("token_type") or "Unknown")],
        ["Primary chain", _pdf_text(asset.get("primary_chain") or "Unknown")],
    ]
    cover_table = Table(cover_rows, colWidths=[55 * mm, 110 * mm])
    cover_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#e6e8ee")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e6e8ee")),
                ("BACKGROUND", (0, 0), (-1, 0), _band_color(band_num)),
                ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(cover_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Executive summary", H2))
    headline = exec_summary.get("headline_decision_view") or exec_summary.get("headline") or ""
    if headline:
        story.append(Card([Paragraph(_pdf_text(headline), H3), Paragraph(_pdf_text(exec_summary.get("one_paragraph_narrative") or ""), P)], left_bar=_band_color(band_num)))
    else:
        story.append(Paragraph("Executive summary is not available.", Muted))

    # Positives / risks & mitigations (compact)
    positives = exec_summary.get("key_positives") or []
    risks = exec_summary.get("key_risks_and_mitigations") or []
    open_qs = exec_summary.get("open_questions_for_committee") or []

    if positives:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Key positives", H3))
        for t in positives[:6]:
            story.append(Paragraph(f"- {_pdf_text(t)}", P))

    if risks:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Key risks and mitigations", H3))
        for rm in risks[:6]:
            r = _pdf_text(rm.get("risk") if isinstance(rm, dict) else rm)
            mtxt = _pdf_text(rm.get("mitigation") if isinstance(rm, dict) else "")
            story.append(Paragraph(f"- {r}", P))
            if mtxt:
                story.append(Paragraph(f"Mitigation: {mtxt}", Small))

    if open_qs:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Open questions for committee", H3))
        for q in open_qs[:6]:
            story.append(Paragraph(f"- {_pdf_text(q)}", P))

    # -----------------------------
    # Token fact sheet
    # -----------------------------
    story.append(Paragraph("Token fact sheet", H2))
    story.append(
        Paragraph(
            "This fact sheet summarises key reference information about the token and its implementation. It is not a marketing document.",
            Muted,
        )
    )
    story.append(Spacer(1, 8))

    # Pull useful external links directly from the fact sheet builder
    name = (asset.get("name") or "").strip()
    ticker = (asset.get("ticker") or "").strip()
    token_type = (asset.get("token_type") or "").strip()
    chain = (asset.get("primary_chain") or "").strip()

    desc = (asset.get("description") or asset.get("description_short") or "").strip()
    # Keep the PDF readable: clip, but allow a longer narrative than before.
    if len(desc) > 560:
        desc = desc[:557].rstrip() + "..."

    # Badges (ticker / chain / type)
    badges = []
    if ticker:
        badges.append(f"Ticker: {ticker}")
    if chain:
        badges.append(f"Chain: {chain}")
    if token_type:
        badges.append(f"Type: {token_type}")

    badge_cells = [Paragraph(_pdf_text(b), Small) for b in badges] if badges else [Paragraph("—", Small)]
    bt = Table([badge_cells], colWidths=[(165 * mm) / max(len(badge_cells), 1)] * len(badge_cells))
    bt.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    # Per-cell chip styling
    for i in range(len(badge_cells)):
        bt.setStyle(
            TableStyle(
                [
                    ("BOX", (i, 0), (i, 0), 0.6, colors.HexColor("#dfe6ff")),
                    ("BACKGROUND", (i, 0), (i, 0), colors.HexColor("#f3f6ff")),
                ]
            )
        )

    # Headline stats "HUD blobs"
    stats = asset.get("headline_stats") or []
    stat_cells = []
    for s in stats[:8]:
        label = _pdf_text(str(s.get("label") or "").upper())
        val = _pdf_text(str(s.get("value") or "—"))
        stat_cells.append(Paragraph(f'<font size="8" color="#56607a"><b>{label}</b></font><br/><font size="11"><b>{val}</b></font>', Small))

    if not stat_cells:
        stat_cells = [Paragraph("No headline stats available.", Muted)]

    # Arrange stats in a 4-column grid
    cols = 4 if len(stat_cells) >= 4 else max(len(stat_cells), 1)
    rows = []
    row = []
    for c in stat_cells:
        row.append(c)
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        # pad last row
        while len(row) < cols:
            row.append(Paragraph("", Small))
        rows.append(row)

    st = Table(rows, colWidths=[(165 * mm) / cols] * cols)
    st.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    for r in range(len(rows)):
        for c in range(cols):
            st.setStyle(
                TableStyle(
                    [
                        ("BOX", (c, r), (c, r), 0.6, colors.HexColor("#cfe0ff")),
                        ("BACKGROUND", (c, r), (c, r), colors.white),
                    ]
                )
            )

    # Links row
    website = (asset.get("website") or "").strip()
    whitepaper = (asset.get("whitepaper") or "").strip()
    link_rows = [
        [Paragraph("Website", Small), Paragraph(_soft_wrap_url(website) if website else "—", Small)],
        [Paragraph("Whitepaper", Small), Paragraph(_soft_wrap_url(whitepaper) if whitepaper else "—", Small)],
    ]
    lt = Table(link_rows, colWidths=[30 * mm, 135 * mm])
    lt.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    # Assemble HUD card
    card_title = Paragraph(_pdf_text(name or "—"), H3)
    card_content = [
        card_title,
        bt,
        Spacer(1, 8),
        st,
        Spacer(1, 8),
        Paragraph(_pdf_text(desc) if desc else "—", P),
        Spacer(1, 6),
        lt,
    ]
    story.append(
        Card(
            card_content,
            bg=colors.HexColor("#fbfcff"),
            stroke=colors.HexColor("#dfe6ff"),
            left_bar=colors.HexColor("#4e74ff"),
            radius=12,
            pad=10,
        )
    )

    story.append(PageBreak())



    # -----------------------------
    # Risk dashboard
    # -----------------------------
    
    # -----------------------------
    # Issuer & key people
    # -----------------------------
    ip = snapshot.get("issuer_profile") or {}
    issuer = ip.get("issuer") or {}
    people = ip.get("key_people") or []

    story.append(Spacer(1, 10))
    story.append(Paragraph("Issuer & key people", H2))
    story.append(
        Paragraph(
            "Public corporate and leadership information used to anchor accountability and monitoring. Where reliable sources are unavailable, fields are shown as “Unknown”.",
            Muted,
        )
    )
    story.append(Spacer(1, 8))

    def _u(v: Any) -> str:
        s = _pdf_text(v)
        return s if s else "Unknown"

    def _link_or_text(v: Any) -> Paragraph:
        u = _pdf_text(v)
        if u and u != "Unknown":
            return Paragraph(f'<link href="{u}">{_soft_wrap_url(u)}</link>', P)
        return Paragraph("Unknown", P)

    issuer_rows = [
        [Paragraph("<b>Legal name</b>", Small), Paragraph(_u(issuer.get("legal_name")), P),
         Paragraph("<b>Jurisdiction</b>", Small), Paragraph(_u(issuer.get("jurisdiction")), P)],
        [Paragraph("<b>Entity type</b>", Small), Paragraph(_u(issuer.get("entity_type")), P),
         Paragraph("<b>Registration #</b>", Small), Paragraph(_u(issuer.get("registration_number")), P)],
        [Paragraph("<b>LEI</b>", Small), Paragraph(_u(issuer.get("lei")), P),
         Paragraph("<b>Status</b>", Small), Paragraph(_u(issuer.get("status")), P)],
        [Paragraph("<b>Registered address</b>", Small), Paragraph(_u(issuer.get("registered_address")), P),
         Paragraph("<b>Website</b>", Small), _link_or_text(issuer.get("website"))],
    ]
    issuer_tbl = Table(issuer_rows, colWidths=[33*mm, 62*mm, 33*mm, 62*mm])
    issuer_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e7ecff")),
            ]
        )
    )

    issuer_evidence = issuer.get("evidence") or []
    issuer_evidence_flows = []
    if isinstance(issuer_evidence, list) and issuer_evidence:
        issuer_evidence_flows.append(Spacer(1, 4))
        issuer_evidence_flows.append(Paragraph("Evidence", Small))
        for e in issuer_evidence[:6]:
            if not isinstance(e, dict):
                continue
            url = _pdf_text(e.get("url"))
            label = _pdf_text(e.get("label")) or url
            if url:
                issuer_evidence_flows.append(Paragraph(f'- <link href="{url}">{_pdf_text(label)}</link>', Small))

    story.append(
        Card(
            [Paragraph("Issuer profile", H3), issuer_tbl] + issuer_evidence_flows,
            left_bar=colors.HexColor("#4e74ff"),
        )
    )
    story.append(Spacer(1, 8))

    if people:
        kp_rows = [[Paragraph("<b>Name</b>", Small), Paragraph("<b>Role</b>", Small),
                    Paragraph("<b>Affiliation</b>", Small), Paragraph("<b>Confidence</b>", Small)]]
        kp_evidence_lines = []
        for p in people[:8]:
            if not isinstance(p, dict):
                continue
            name = _u(p.get("name"))
            role = _u(p.get("role"))
            aff = _u(p.get("affiliation"))
            conf = _u(p.get("confidence"))
            kp_rows.append([Paragraph(name, P), Paragraph(role, P), Paragraph(aff, P), Paragraph(conf, P)])

            ev = p.get("evidence") or []
            if isinstance(ev, list) and ev:
                # show up to 2 evidence links per person (keeps PDF tidy)
                links = []
                for e in ev[:2]:
                    if not isinstance(e, dict):
                        continue
                    url = _pdf_text(e.get("url"))
                    label = _pdf_text(e.get("label")) or url
                    if url:
                        links.append(f'<link href="{url}">{_pdf_text(label)}</link>')
                if links:
                    kp_evidence_lines.append(Paragraph(f'{_pdf_text(name)} — ' + " | ".join(links), Small))

        kp_tbl = Table(kp_rows, colWidths=[56*mm, 46*mm, 52*mm, 26*mm])
        kp_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6ff")),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#dfe6ff")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#eef2ff")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        story.append(
            Card(
                [Paragraph("Key people", H3), kp_tbl]
                + ([Spacer(1, 4), Paragraph("Evidence", Small)] + kp_evidence_lines if kp_evidence_lines else []),
                left_bar=colors.HexColor("#7c3aed"),
            )
        )
    else:
        story.append(
            Card(
                [Paragraph("Key people", H3), Paragraph("Unknown — no reliable public disclosures were found in this run.", Muted)],
                left_bar=colors.HexColor("#7c3aed"),
            )
        )

    story.append(PageBreak())

    story.append(Paragraph("Risk dashboard — high-level profile", H2))
    story.append(
        Paragraph(
            "This section provides a high-level view of the token's overall risk band and how risk is distributed across key domains.",
            Muted,
        )
    )

    # Overall tile + distribution bar
    band_distribution = (risk_dashboard.get("band_distribution") or {})
    dist_items = []
    for k in ["Very Low", "Low", "Medium", "Medium-High", "High"]:
        v = float(band_distribution.get(k) or 0.0)
        dist_items.append((k, v))

    # Simple distribution row
    dist_text = ", ".join([f"{k}: {int(v*100)}%" for k, v in dist_items if v > 0])
    if dist_text:
        story.append(Spacer(1, 6))
        story.append(Card([Paragraph(f"Overall band: {_pdf_text(band_name)} ({band_num}/5)" if band_num else f"Overall band: {_pdf_text(band_name)}", H3),
                           Paragraph(_pdf_text(dist_text), Muted)], left_bar=_band_color(band_num)))
    else:
        story.append(Spacer(1, 6))
        story.append(Card([Paragraph(f"Overall band: {_pdf_text(band_name)} ({band_num}/5)" if band_num else f"Overall band: {_pdf_text(band_name)}", H3)], left_bar=_band_color(band_num)))

    # Domain tiles (compact table)
    domains = risk_dashboard.get("domains") or []
    if domains:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Domains", H3))

        rows = [["Domain", "Band", "Avg score", "Weight", "Escalations"]]
        band_nums = [None]  # header placeholder to align row indexes

        for d in domains:
            bn = int(d.get("band_numeric") or 0)
            band_nums.append(bn)
            rows.append([
                _pdf_text(d.get("name") or d.get("code") or ""),
                _pdf_text(d.get("band_name") or ""),
                _fmt_num(d.get("avg_score"), nd=3),
                _fmt_num(d.get("weight"), nd=3),
                _pdf_text(d.get("board_escalation_count") or 0),
            ])

        t = Table(rows, colWidths=[70 * mm, 30 * mm, 25 * mm, 20 * mm, 20 * mm])

        base_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.6),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0b1220")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e6e8ee")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),  # Band column bold
        ]

        # Colour-code the band cell per domain row
        for row_idx in range(1, len(rows)):
            bn = band_nums[row_idx] or 0
            base_style.append(("BACKGROUND", (1, row_idx), (1, row_idx), _band_color(bn)))

        t.setStyle(TableStyle(base_style))
        story.append(t)


    story.append(PageBreak())

    # -----------------------------
    # Domain findings
    # -----------------------------
    story.append(Paragraph("Domain findings — strengths, risks and watchpoints", H2))
    story.append(
        Paragraph(
            "For each risk domain, this section summarises key strengths, material risks and practical watchpoints to support listing and ongoing monitoring decisions.",
            Muted,
        )
    )
    for d in (snapshot.get("domain_findings") or []):
        story.append(Spacer(1, 8))
        title = f"{_pdf_text(d.get('domain_name') or '')} — {_pdf_text(d.get('band_name') or '')}"
        left = _band_color(int(d.get("band_numeric") or 0))
        parts = [Paragraph(title, H3)]
        one = _pdf_text(d.get("one_line") or "")
        if one:
            parts.append(Paragraph(one, Muted))

        # three columns as a table
        strengths = d.get("strengths") or []
        risks2 = d.get("risks") or []
        watch = d.get("watchpoints") or []

        def _bullets(items):
            if not items:
                return Paragraph(_pdf_text("None noted."), Small)
            txt = "<br/>".join([f"- {_pdf_text(x)}" for x in items[:6]])
            return Paragraph(txt, Small)

        cols = Table(
            [
                ["Strengths", "Key risks", "Watchpoints / monitoring"],
                [_bullets(strengths), _bullets(risks2), _bullets(watch)],
            ],
            colWidths=[55 * mm, 55 * mm, 55 * mm],
        )
        cols.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f5f8")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.2),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e6e8ee")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        parts.append(Spacer(1, 4))
        parts.append(cols)
        story.append(Card(parts, left_bar=left))

    story.append(PageBreak())

    # -----------------------------
    # Listing committee escalations (cards)
    # -----------------------------
    story.append(Paragraph("Listing committee escalation items", H2))
    story.append(
        Paragraph(
            "DDQ questions flagged by automated rules for listing committee visibility. Each card shows the trigger, the underlying concern, and how recent the supporting evidence is.",
            Muted,
        )
    )

    if esc_count == 0:
        story.append(Card([Paragraph("No listing committee escalation items were identified for this assessment.", P)], left_bar=colors.HexColor("#c9ced8")))

    for e in board_escalations[:60]:
        parts = []
        title = f"{_pdf_text(e.get('domain_name',''))} — {_pdf_text(e.get('question_id',''))}"
        parts.append(Paragraph(title, H3))
        qtxt = _pdf_text(e.get("question_text") or "")
        if qtxt:
            parts.append(Paragraph(qtxt, Muted))

        meta_bits = []
        if e.get("flag"):
            meta_bits.append(f"Flag: {_pdf_text(e.get('flag'))}")
        if e.get("staleness_class"):
            meta_bits.append(f"Staleness: {_pdf_text(e.get('staleness_class'))}")
        if e.get("most_recent_source_date"):
            meta_bits.append(f"Most recent source date: {_pdf_text(e.get('most_recent_source_date'))}")
        if meta_bits:
            parts.append(Paragraph(" · ".join(meta_bits), Small))

        if e.get("trigger_rule"):
            parts.append(Paragraph(f"Trigger: {_pdf_text(e.get('trigger_rule'))}", Small))
        if e.get("raw_narrative"):
            parts.append(Paragraph(_pdf_text(e.get("raw_narrative")), P))

        cites = e.get("citations") or []
        if cites:
            parts.append(Paragraph("Sources:", Small))
            cites_txt = "<br/>".join([f"- {_pdf_text(c)}" for c in cites[:6]])
            parts.append(Paragraph(cites_txt, Small))

        left = colors.HexColor("#c9ced8")  # neutral accent only (no staleness colouring)
        story.append(Card(parts, left_bar=left))


    story.append(PageBreak())

    # -----------------------------
    # Asset-specific risk disclosures
    # -----------------------------
    story.append(Paragraph("Asset-specific risk disclosures", H2))
    story.append(
        Paragraph(
            "Targeted disclosures relevant to this asset, derived from the DDQ and risk-tag inference.",
            Muted,
        )
    )

    if include_baseline_crypto_risks and baseline_general_risks:
        story.append(Spacer(1, 8))
        bullets = "<br/>".join([f"- {_pdf_text(t)}" for t in baseline_general_risks[:12]])
        story.append(Card([
            Paragraph(_pdf_text(baseline_general_heading), H3),
            Paragraph(_pdf_text(baseline_general_explainer), Small),
            Paragraph(bullets, Small),
        ], left_bar=_band_color(3)))

    for cat in asset_specific_risks:
        cname = _pdf_text(cat.get("category") or "Category")
        if (not include_baseline_crypto_risks) and cname.lower().startswith("cryptoasset risks"):
            continue
        if cname.lower().startswith("cryptoasset risks"):
            # keep it out of the dynamic list; we render the generic block above in UK mode
            continue

        story.append(Spacer(1, 8))
        items = cat.get("items") or []
        parts = [Paragraph(cname, H3)]
        intro = (cat.get("intro") or "")
        if intro:
            parts.append(Paragraph(_pdf_text(intro), Small))

        if not items:
            parts.append(Paragraph("No items.", Muted))
        else:
            for item in items[:12]:
                txt = (item.get("text") or "").strip()
                if txt:
                    parts.append(Paragraph(f"- {_pdf_text(txt)}", P))
                rsn = (item.get("reason") or "").strip()
                if rsn:
                    parts.append(Paragraph(f"Why this matters: {_pdf_text(rsn)}", Small))

                ev = item.get("evidence") or []
                if ev:
                    refs = []
                    for e in ev[:4]:
                        sh = (e.get("sheet_name") or e.get("sheet") or "").strip()
                        qid = (e.get("question_id") or "").strip()
                        if sh and qid:
                            refs.append(f"{sh} {qid}")
                        elif qid:
                            refs.append(qid)
                    if refs:
                        parts.append(Paragraph(f"DDQ evidence: {_pdf_text('; '.join(refs))}", Small))

        story.append(Card(parts, left_bar=colors.HexColor("#c9ced8")))

    story.append(PageBreak())

    # -----------------------------
    # Listing requirements
    # -----------------------------
    story.append(Paragraph("Listing requirements and controls", H2))
    story.append(
        Paragraph(
            "These items translate the risk assessment into concrete actions for the firm's listing, risk and monitoring framework.",
            Muted,
        )
    )

    required = [r for r in listing_requirements if (r.get("severity") or "").lower() == "required"]
    recommended = [r for r in listing_requirements if (r.get("severity") or "").lower() != "required"]

    def _req_card(r, left):
        title = _pdf_text(r.get("title") or r.get("id") or "")
        body = _pdf_text(r.get("text") or "")
        sev = _pdf_text(r.get("severity") or "")
        return Card(
            [
                Paragraph(f"{sev}: {title}", H3),
                Paragraph(body, P),
            ],
            left_bar=left,
            bg=colors.white,
        )

    if required:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Required", H3))
        for r in required:
            story.append(Spacer(1, 6))
            story.append(_req_card(r, colors.HexColor("#ff7a7a")))

    if recommended:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Recommended", H3))
        for r in recommended:
            story.append(Spacer(1, 6))
            story.append(_req_card(r, colors.HexColor("#a7c7ff")))

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return out_path
