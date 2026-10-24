"""Compatibility entry point for the shared pi-streams Prime transport."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi-streams"))
from engine.prime import CliError, LEVELS, PrimeClient, array_field, object_data, reject_json_constant
from engine.prime_compat import main
