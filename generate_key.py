"""CLI tool to generate MarketLens serial keys (admin use)."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from security.license_manager import LicenseManager


def main():
    tier = sys.argv[1] if len(sys.argv) > 1 else "pro"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if tier not in ("basic", "pro", "enterprise"):
        print("Usage: py generate_key.py [basic|pro|enterprise] [count]")
        sys.exit(1)

    lm = LicenseManager()
    for _ in range(count):
        print(lm.generate_key(tier))


if __name__ == "__main__":
    main()
