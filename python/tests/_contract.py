"""The path to `contract/` — ONE place holds it, every test suite points here.

The JavaScript suite used to read `../../python/tests/vectors.json`: the JavaScript package reached
into the Python package's insides. Publishing either package on its own breaks that path, and no
command reports it. Both sides now point at `contract/`, and neither owns the other's data.
"""
from __future__ import annotations

import json
import os

CONTRACT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "contract"))


def load(name: str):
    """Read one file in `contract/`. A missing file RAISES — never return empty and carry on: a
    suite with 0 cases is still green, and everyone reading it believes something was tested."""
    with open(os.path.join(CONTRACT_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)
