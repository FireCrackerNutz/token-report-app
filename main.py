from pathlib import Path
import json

from app.ddq_parser import parse_ddq
from app.report_snapshot import build_report_snapshot


def main():
    ddq_path = Path("data/DDQ_Avalanche (2).xlsx")
    parsed = parse_ddq(ddq_path)

    snapshot = build_report_snapshot(parsed)

    # Existing prints...
    rd = snapshot["risk_dashboard"]
    print("=== Risk dashboard ===")
    print(f"Overall band: {rd['overall_band']['name']} ({rd['overall_band']['numeric']})")

    # New: domain findings preview
    print("\n=== Domain findings ===")
    for df in snapshot["domain_findings"]:
        print(f"- {df['domain_name']}: {df['one_line']}")
        print(f"  Strengths: {len(df['strengths'])}, "
              f"Risks: {len(df['risks'])}, "
              f"Watchpoints: {len(df['watchpoints'])}")

    out_path = Path("data/report_snapshot.json")
    out_path.write_text(json.dumps(snapshot, indent=2))
    print(f"\nSnapshot JSON written to {out_path}")


if __name__ == "__main__":
    main()
