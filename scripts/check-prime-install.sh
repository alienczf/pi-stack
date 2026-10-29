#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests -p test_prime_install.py
