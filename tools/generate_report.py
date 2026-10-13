"""Generate Markdown from saved research results without rerunning research."""
import argparse
from pathlib import Path

from lab.report import generate_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    print(generate_report(args.run_dir))


if __name__ == "__main__":
    main()
