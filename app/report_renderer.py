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
    from reportlab.lib.utils import ImageReader
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
    if isinstance(logo_url, str) and logo_url.startswith("http"):
        try:
            req = urllib.request.Request(logo_url, headers={"User-Agent": "token-report-app/1.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = r.read()
            logo_reader = ImageReader(io.BytesIO(data))
        except Exception:
            logo_reader = None

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

    if logo_reader is not None:
        try:
            # Use the same reader we already downloaded; render at a fixed size
            logo_img = Image(logo_reader, width=12 * mm, height=12 * mm)
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

    story.append(PageBreak())

    # -----------------------------
    # Risk dashboard
    # -----------------------------
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
                _pdf_text(d.get("avg_score") or ""),
                _pdf_text(d.get("weight") or ""),
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

    story.append(PageBreak())

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

    urls = asset.get("urls") or {}
    facts = [
        ["Name", _pdf_text(asset.get("name") or "")],
        ["Ticker", _pdf_text(asset.get("ticker") or "")],
        ["Token type", _pdf_text(asset.get("token_type") or "")],
        ["Primary chain", _pdf_text(asset.get("primary_chain") or "")],
        ["Short description", _pdf_text(asset.get("description_short") or "")],
        ["Website", _pdf_text(urls.get("website") or "")],
    ]
    ft = Table(facts, colWidths=[45 * mm, 120 * mm])
    ft.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#e6e8ee")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e6e8ee")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(ft)

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return out_path
