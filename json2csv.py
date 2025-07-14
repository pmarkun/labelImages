#!/usr/bin/env python3
"""
Standalone script to export a simplified CSV from a JSON input
using the same logic as the Runner Viewer interface.
"""

import argparse
import sys

from core.data_manager import DataManager


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Export simplified CSV from JSON input "
            "using the same logic as the interface."
        )
    )
    parser.add_argument(
        "input_json",
        help="Path to the input JSON file (new format).",
    )
    parser.add_argument(
        "output_csv",
        help="Path to the output CSV file.",
    )
    args = parser.parse_args()

    dm = DataManager()
    try:
        dm.load_json(args.input_json)
    except Exception as e:
        print(f"Error loading JSON file '{args.input_json}': {e}", file=sys.stderr)
        sys.exit(1)

    try:
        exported = dm.export_simplified_csv(args.output_csv)
    except Exception as e:
        print(f"Error exporting CSV to '{args.output_csv}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Exported {exported} rows to '{args.output_csv}'.")


if __name__ == "__main__":
    main()
