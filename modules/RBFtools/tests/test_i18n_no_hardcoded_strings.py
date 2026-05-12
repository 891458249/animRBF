"""Permanent guard: no hardcoded user-visible strings in widgets.

Scans every widget source file for ``setText`` / ``addItem`` /
``setToolTip`` / ``setWindowTitle`` / ``setPlaceholderText`` calls
and flags any that pass a literal non-tr string. M2.4a establishes
this as a permanent rule: every visible string must go through
``tr("key")`` so the i18n table owns the truth.

KNOWN_VIOLATIONS holds a maintained whitelist for legacy violations
that pre-date this guard. New entries are 0-tolerance.

M_UIPOLISH (E.3 + Hardening 3): the scan range is extended to
also cover ``ui/main_window.py``. The KNOWN_VIOLATIONS whitelist
is **0-modified** under M_UIPOLISH (the only existing entries -
``pose_table.py:105/110`` numeric format-spec literals - remain
on the whitelist).
"""

from __future__ import absolute_import

import pathlib
import re
import unittest


# ----------------------------------------------------------------------
# Whitelist for pre-existing legacy violations (clean up over time).
# Format: "<filename>:<line_no>" — exact match.
# ----------------------------------------------------------------------
KNOWN_VIOLATIONS = {
    # pose_table.py uses '{:.3f}' as a Python format-spec to display
    # numeric pose values — the literal isn't a user-translatable
    # phrase. Acceptable per i18n contract; left whitelisted rather
    # than excluded by regex to keep the scanner simple.
    "pose_table.py:105",
    "pose_table.py:110",
}


# Methods that take user-visible string arguments.
_VISIBLE_METHODS = (
    "setText", "addItem", "setToolTip", "setWindowTitle",
    "setPlaceholderText", "setStatusTip", "setWhatsThis",
)
_PATTERN = re.compile(
    r'\.(' + '|'.join(_VISIBLE_METHODS) + r')\s*\(\s*[uU]?["\']([^"\']+)["\']'
)


def _has_letter(s):
    """True iff *s* contains at least one alphabetic character.
    Pure-numeric / punctuation strings are exempt (e.g., 'X', ',', ' ')."""
    return any(c.isalpha() for c in s)


class TestNoHardcodedVisibleStrings(unittest.TestCase):

    def _scan_path(self, py, violations):
        """Scan a single .py file and append any violations."""
        text = py.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            # Allow comments — strip from "#" to EOL.
            code = line.split("#", 1)[0]
            for m in _PATTERN.finditer(code):
                method, literal = m.groups()
                # Skip if the line ALSO contains tr( before the method
                # call (means tr(...) is the argument, not a literal).
                prefix = code.split("." + method, 1)[0]
                if "tr(" in prefix:
                    continue
                # Single character or no-letter strings are fine
                # (separators, units, numeric placeholders).
                if not _has_letter(literal) or len(literal) <= 1:
                    continue
                location = "{}:{}".format(py.name, line_no)
                if location in KNOWN_VIOLATIONS:
                    continue
                violations.append("{} {}({!r})".format(
                    location, method, literal))

    def test_no_hardcoded_strings_in_widgets(self):
        # tests/ → parent → RBFtools/ (module) → scripts/RBFtools/ui/widgets
        widgets_dir = (pathlib.Path(__file__).resolve().parent.parent
                       / "scripts" / "RBFtools" / "ui" / "widgets")
        if not widgets_dir.exists():
            self.skipTest("widgets dir not found: {}".format(widgets_dir))

        violations = []
        for py in widgets_dir.rglob("*.py"):
            if py.name == "__init__.py":
                continue
            self._scan_path(py, violations)

        self.assertEqual(violations, [],
            "Hardcoded visible strings found (violation of M2.4a addendum "
            "i18n guard). Wrap with tr(\"key\") and add the key to i18n.py:\n  "
            + "\n  ".join(violations))

    def test_no_hardcoded_strings_in_main_window(self):
        """M_UIPOLISH (E.3 + Hardening 3): extend the scan to
        ui/main_window.py - it carries 37 tr() calls already but
        was historically out of scan range. KNOWN_VIOLATIONS is
        0-modified; any new finding here must be fixed by
        wrapping with tr() in the SAME commit (red line 14
        backcompat parity)."""
        main_window = (pathlib.Path(__file__).resolve().parent.parent
                       / "scripts" / "RBFtools" / "ui" / "main_window.py")
        if not main_window.exists():
            self.skipTest("main_window.py not found: {}".format(main_window))

        violations = []
        self._scan_path(main_window, violations)

        self.assertEqual(violations, [],
            "Hardcoded visible strings found in main_window.py "
            "(M_UIPOLISH E.3 guard extension). Wrap with tr(\"key\"):\n  "
            + "\n  ".join(violations))


if __name__ == "__main__":
    unittest.main()
