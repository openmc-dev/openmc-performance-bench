#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 TAKT contributors
# Generated with the assistance of an AI coding tool.
"""Keep stock density-family XML, logs, statepoints and scientific-check receipts."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.scripts._density_family import run_family

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "performance"), default="smoke")
    parser.add_argument(
        "--output", type=Path, required=True, help="New output directory"
    )
    args = parser.parse_args()
    print(
        run_family(
            args.output, profile=args.profile, threads=1, repeat=args.profile == "smoke"
        )
    )
