from pathlib import Path
import json
import os

from app.ddq_parser import parse_ddq
from app.report_snapshot import build_report_snapshot
from app.report_renderer import write_report_html, write_report_pdf


def main():
    ddq_path = Path(os.getenv("DDQ_PATH", "data/DDQ_World Liberty Financial (1).xlsx"))
    parsed = parse_ddq(ddq_path)

    # For now, hard-code or pull from env; later this will come from the UI.
    token_meta = {
        "name": os.getenv("TOKEN_NAME", "Avalanche"),
        "ticker": os.getenv("TOKEN_TICKER", "AVAX"),
        # token_type is now derived from DDQ A1.1 by default; set TOKEN_TYPE only to override.
        "token_type": os.getenv("TOKEN_TYPE", ""),
        # optional but recommended for deterministic metadata enrichment
        "coingecko_id": os.getenv("COINGECKO_ID", "") or None,
        # optional manual tags you *always* want for this run:
        "risk_tags": [],
    }

    snapshot = build_report_snapshot(parsed, token_meta=token_meta)

    out_dir = Path(os.getenv("OUT_DIR", "data"))
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / "report_snapshot.json"
    out_json.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    print(f"Snapshot JSON written to {out_json}")

    # HTML
    out_html = out_dir / "report.html"
    try:
        write_report_html(snapshot, out_path=out_html)
        print(f"Report HTML written to {out_html}")
    except Exception as e:
        print(f"WARNING: Failed to render HTML: {e}")

    # PDF (ReportLab)
    out_pdf = out_dir / "report.pdf"
    try:
        write_report_pdf(snapshot, out_path=out_pdf)
        print(f"Report PDF written to {out_pdf}")
    except Exception as e:
        print(f"WARNING: Failed to render PDF: {e}")


if __name__ == "__main__":
    main()
