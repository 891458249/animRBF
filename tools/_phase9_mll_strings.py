# -*- coding: utf-8 -*-
"""Phase 9 Task B helper: extract printable ASCII strings (>=4 chars)
from a binary and filter to interesting tags. Stand-in for the unix
`strings` command on hosts that lack it.

Usage:
    python tools/_phase9_mll_strings.py <path.mll> [pattern_regex]

If no pattern is given, the default Phase 9 audit regex is used.
"""
from __future__ import absolute_import, print_function

import re
import sys


DEFAULT_PATTERN = (
    rb"(M_P0_|polyDim|DISCONNECT_SCALE|COLUMN_RANK|MQ|MAYA_API|Maya2022|"
    rb"Maya2025|TPS|honest)"
)

PRINTABLE = re.compile(rb"[ -~]{4,}")  # 4+ printable ASCII chars


def main():
    if len(sys.argv) < 2:
        print("usage: tools/_phase9_mll_strings.py <path.mll> [pattern]")
        sys.exit(2)

    path = sys.argv[1]
    pat_src = sys.argv[2].encode("utf-8") if len(sys.argv) >= 3 else DEFAULT_PATTERN
    pat = re.compile(pat_src, flags=re.IGNORECASE)

    with open(path, "rb") as f:
        data = f.read()

    hits = set()
    for m in PRINTABLE.finditer(data):
        s = m.group(0)
        if pat.search(s):
            hits.add(s.decode("ascii", errors="replace"))

    for s in sorted(hits):
        print(s)


if __name__ == "__main__":
    main()
