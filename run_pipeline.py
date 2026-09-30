import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ROLE_COMMANDS = {
    1: ["python", "-m", "src.ingestion.scraper_lead"],
    2: ["python", "-m", "src.engineering.clean_staging_lead"],
}

ROLE_LABELS = {1: "Role 1 (Data Ingestion / Scraper)", 2: "Role 2 (Data Engineering / Cleanup)"}


def run_command(cmd, label):
    print(f"\n[>>>] Starting {label}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"[!!!] {label} FAILED with exit code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[OK] {label} completed successfully")
    return result.returncode


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="MOSPI Airfare Index end-to-end pipeline orchestrator.",
    )
    parser.add_argument(
        "--role",
        type=int,
        choices=[1, 2],
        help="Run a specific role (1 = ingestion, 2 = data engineering).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the full pipeline: Role 1 ingestion, then Role 2 data engineering.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.role == 1:
        run_command(ROLE_COMMANDS[1], ROLE_LABELS[1])
    elif args.role == 2:
        run_command(ROLE_COMMANDS[2], ROLE_LABELS[2])
    elif args.all or (args.role is None and not args.all):
        run_command(ROLE_COMMANDS[1], ROLE_LABELS[1])
        run_command(ROLE_COMMANDS[2], ROLE_LABELS[2])
    else:
        parser.print_help()

    print("\n[OK] Pipeline run complete.")


if __name__ == "__main__":
    main()