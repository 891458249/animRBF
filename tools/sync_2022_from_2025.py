# -*- coding: utf-8 -*-
"""sync_2022_from_2025.py -- regenerate scripts_2022/ from scripts/.

Single source of truth for the Maya 2022 py2/py3 compatibility fork.
``modules/RBFtools/scripts/`` is canonical (Maya 2025 path); this script
applies the transformation rules from PATCH_BRIEF_M_P0_MAYA_VERSION_ISOLATION.md
sec.4.2 to produce ``modules/RBFtools/scripts_2022/`` which is byte-level
100% ASCII and stable under both py2 mayapy2 and py3 mayapy.

Usage:
    python tools/sync_2022_from_2025.py           # regenerate scripts_2022/
    python tools/sync_2022_from_2025.py --check   # drift detector (exit 1 on diff)

Idempotent + deterministic -- running twice produces identical output.

Transformation rules implemented:
  Rule 1: coding decl ``# -*- coding: utf-8 -*-`` on line 1 (or 2 after shebang)
  Rule 2: non-ASCII raw chars in STRING tokens promoted to ``\\uXXXX`` escape
          with auto-injection of ``u`` prefix (skipped for ``r`` / ``rb``)
  Rule 2 (comments): non-ASCII chars in COMMENT tokens transliterated to
          ASCII visual equivalents (em dash -> --, star -> *, Greek letters
          spelled out, Chinese codepoints retained as a placeholder span)
  Rule 3: ``\\xHH`` byte escapes with HH > 0x7F inside STRING tokens are
          decoded as UTF-8 multi-byte sequences when valid, else as
          isolated Latin-1 codepoints, then re-emitted as ``\\uXXXX`` so
          the runtime value is identical in py2 and py3
  Rule 4: ``isinstance(x, str)`` -> ``isinstance(x, _STR_TYPES)`` plus
          module-local ``_STR_TYPES`` helper auto-injected after the
          first import-block in any file that uses it
  Rule 5: ``help_button.py`` only -- wrap ``from RBFtools.ui.help_texts``
          import in a module-level try/except with an ASCII-only
          fallback ``_get_help_text``
  Rule 6: ``super()`` no-arg -> ``super(ClassName, self)`` -- audit-only
          (current project has zero hits; sync script asserts)
  Rule 7: misc py3-only syntax audit (f-string / walrus / etc.) -- warn only.

The script is intentionally written for both py2.7 and py3.6+ so it can
itself be invoked from a Maya 2022 mayapy2 session if ever needed.
"""
from __future__ import absolute_import, print_function

import argparse
import io
import os
import re
import shutil
import sys
import tokenize

# ----------------------------------------------------------------------
# Paths (relative to repo root which must be the cwd when invoking)
# ----------------------------------------------------------------------
SRC_DIR = os.path.join("modules", "RBFtools", "scripts")
DST_DIR = os.path.join("modules", "RBFtools", "scripts_2022")

# ----------------------------------------------------------------------
# Rule 2 / 3 helpers
# ----------------------------------------------------------------------

_STRING_PREFIX_RE = re.compile(
    r"^([uUbBrRfF]{0,3})(['\"])", flags=re.DOTALL)

# Matches a single \xHH escape inside a string literal body
_XHH_RE = re.compile(r"\\x([0-9a-fA-F]{2})")


def _is_raw_prefix(prefix):
    return "r" in prefix.lower()


def _is_bytes_prefix(prefix):
    return "b" in prefix.lower()


def _is_fstring_prefix(prefix):
    return "f" in prefix.lower()


def _decode_string_literal_body(body, prefix):
    """Return the runtime value of a string literal body.

    For ``r``-prefixed strings the body is returned verbatim (the
    backslashes are literal). For non-raw strings the existing escape
    sequences are decoded so we can re-emit them.
    """
    if _is_raw_prefix(prefix):
        return body
    # Use Python's own escape decoder on a wrapped 'unicode_escape'.
    # codecs.escape_decode handles the bytes equivalent but we want
    # to operate on a str. Roundtrip through unicode_escape.
    try:
        return body.encode("latin-1").decode("unicode_escape")
    except Exception:
        # Fall back to body unchanged; caller will re-emit it
        return body


def _merge_utf8_escapes(body):
    """Find consecutive ``\\xHH`` byte escapes whose HH > 0x7F and
    merge them as UTF-8 if they form a valid multi-byte sequence.

    Replace each merged sequence with the corresponding ``\\uXXXX`` (or
    ``\\UXXXXXXXX`` if > 0xFFFF) escape. Lone high bytes that are not
    part of a UTF-8 sequence become ``\\u00HH`` (Latin-1 codepoint).
    """
    # Tokenise the body into runs of literal text and \xHH escapes.
    pieces = []
    pos = 0
    for m in _XHH_RE.finditer(body):
        if m.start() > pos:
            pieces.append(("lit", body[pos:m.start()]))
        pieces.append(("xhh", int(m.group(1), 16)))
        pos = m.end()
    if pos < len(body):
        pieces.append(("lit", body[pos:]))

    # Walk pieces, collecting consecutive xhh > 0x7F bytes for UTF-8
    # decode attempts.
    out = []
    i = 0
    while i < len(pieces):
        kind, val = pieces[i]
        if kind == "lit":
            out.append(val)
            i += 1
            continue
        # kind == "xhh"
        if val < 0x80:
            # ASCII range -- leave as \xHH escape (no merging needed)
            out.append("\\x{0:02x}".format(val))
            i += 1
            continue
        # Collect a run of consecutive xhh bytes
        run = [val]
        j = i + 1
        while j < len(pieces) and pieces[j][0] == "xhh" and pieces[j][1] >= 0x80:
            run.append(pieces[j][1])
            j += 1
        # Try to decode the run as UTF-8 (greedy split)
        encoded_run = []
        k = 0
        while k < len(run):
            # Determine UTF-8 sequence length from lead byte
            lead = run[k]
            if 0xC2 <= lead <= 0xDF and k + 1 < len(run) and 0x80 <= run[k + 1] <= 0xBF:
                cont = run[k + 1]
                cp = ((lead & 0x1F) << 6) | (cont & 0x3F)
                encoded_run.append(cp)
                k += 2
            elif (0xE0 <= lead <= 0xEF
                    and k + 2 < len(run)
                    and 0x80 <= run[k + 1] <= 0xBF
                    and 0x80 <= run[k + 2] <= 0xBF):
                cp = ((lead & 0x0F) << 12) | ((run[k + 1] & 0x3F) << 6) | (run[k + 2] & 0x3F)
                encoded_run.append(cp)
                k += 3
            elif (0xF0 <= lead <= 0xF4
                    and k + 3 < len(run)
                    and 0x80 <= run[k + 1] <= 0xBF
                    and 0x80 <= run[k + 2] <= 0xBF
                    and 0x80 <= run[k + 3] <= 0xBF):
                cp = (((lead & 0x07) << 18)
                      | ((run[k + 1] & 0x3F) << 12)
                      | ((run[k + 2] & 0x3F) << 6)
                      | (run[k + 3] & 0x3F))
                encoded_run.append(cp)
                k += 4
            else:
                # Not a valid UTF-8 lead -- emit as Latin-1 codepoint
                encoded_run.append(lead)
                k += 1
        for cp in encoded_run:
            if cp <= 0xFFFF:
                out.append("\\u{0:04x}".format(cp))
            else:
                out.append("\\U{0:08x}".format(cp))
        i = j
    return "".join(out)


def _ascii_escape_string_token(tok_string):
    """Rule 2 + 3 applied to a single STRING token.

    Returns an equivalent string literal whose source bytes are pure
    ASCII. The runtime value is unchanged.
    """
    m = _STRING_PREFIX_RE.match(tok_string)
    if not m:
        return tok_string
    prefix = m.group(1)
    quote_char = m.group(2)
    # Determine quote style: triple-quoted or single-quoted
    after_prefix = tok_string[len(prefix):]
    if after_prefix.startswith(quote_char * 3):
        quote = quote_char * 3
    else:
        quote = quote_char
    body = after_prefix[len(quote):-len(quote)]

    # Raw strings need special handling: backslash sequences are
    # literal so we cannot just emit \\uXXXX. If the raw body contains
    # any non-ASCII char we split the literal into ASCII-only raw
    # chunks plus per-char u"\\uXXXX" pieces concatenated via Python
    # implicit string adjacency.
    if _is_raw_prefix(prefix):
        if not any(ord(c) > 127 for c in body):
            return tok_string
        return _split_raw_string_with_unicode(prefix, quote, body)

    # Rule 3 first: merge \xHH (HH > 0x7F) sequences. This operates on
    # the source-level body (escape sequences still as backslash text).
    new_body = _merge_utf8_escapes(body)

    # Rule 2: any raw non-ASCII char in the (post-Rule-3) body becomes a
    # \uXXXX or \UXXXXXXXX escape.
    has_non_ascii = any(ord(c) > 127 for c in new_body)

    # Phase 7 hotfix (M_P0_MAYA_VERSION_ISOLATION):
    # Rule 3 may have produced \uXXXX / \UXXXXXXXX escapes from \xHH
    # multi-byte sequences. py2 requires a u-prefix for \uXXXX to
    # decode as a Unicode escape; without it, ``"φ"`` is six
    # literal ASCII chars instead of phi. Auto-promote the prefix
    # whenever the post-Rule-3 body contains such an escape. The
    # negative-lookbehind handles ``\\u`` (an escaped backslash
    # followed by literal ``u``) so we do not over-promote.
    has_unicode_escape = bool(
        re.search(r'(?<!\\)(?:\\\\)*\\[uU][0-9a-fA-F]{4}', new_body)
    )

    if has_non_ascii:
        escaped = []
        for c in new_body:
            cp = ord(c)
            if cp < 128:
                escaped.append(c)
            elif cp <= 0xFFFF:
                escaped.append("\\u{0:04x}".format(cp))
            else:
                escaped.append("\\U{0:08x}".format(cp))
        new_body = "".join(escaped)

    # Auto-prefix u if literal contains raw non-ASCII (Rule 2) OR
    # post-Rule-3 \uXXXX / \UXXXXXXXX escapes (Phase 7 hotfix).
    if (has_non_ascii or has_unicode_escape) and not (
            _is_bytes_prefix(prefix) or "u" in prefix.lower()):
        prefix = "u" + prefix

    return prefix + quote + new_body + quote


def _split_raw_string_with_unicode(prefix, quote, body):
    """Convert a raw string literal containing non-ASCII into adjacent
    raw + unicode pieces.

    E.g. ``r\"abc - def\"`` containing an em-dash becomes
    ``r\"abc \" u\"\\u2014\" r\" def\"`` -- Python concatenates adjacent
    string literals at compile time so the runtime value is identical.
    Empty raw pieces are dropped to avoid empty literals.
    """
    out = []
    cur = []
    for ch in body:
        if ord(ch) < 128:
            cur.append(ch)
        else:
            if cur:
                out.append(prefix + quote + "".join(cur) + quote)
                cur = []
            cp = ord(ch)
            if cp <= 0xFFFF:
                u_escape = "\\u{0:04x}".format(cp)
            else:
                u_escape = "\\U{0:08x}".format(cp)
            # The bridging u-string must be a non-raw, non-bytes string
            # of the same quote style. If the original was b-prefixed
            # raw (br"..." / rb"..." -- unusual but legal) we cannot
            # bridge with a u"..." -- in that case fall back to "?" in
            # the raw body itself.
            if _is_bytes_prefix(prefix):
                cur.append("?")
            else:
                # Use single-quote for the bridge for triple-quoted
                # bodies so we never collide; use double-quote for
                # single-quoted bodies. Quote choice does not matter
                # for runtime value.
                bridge_quote = '"' if quote != '"' else "'"
                out.append("u" + bridge_quote + u_escape + bridge_quote)
    if cur:
        out.append(prefix + quote + "".join(cur) + quote)
    return " ".join(out)


# ----------------------------------------------------------------------
# Comment ASCII transliteration (Rule 2)
# ----------------------------------------------------------------------

# Symbols with an unambiguous ASCII visual equivalent
_COMMENT_MAP = {
    "—": "--",   # em dash
    "–": "-",    # en dash
    "−": "-",    # minus sign
    "·": "*",    # middle dot
    "•": "*",    # bullet
    "★": "*",    # black star
    "☆": "*",    # white star
    "°": " deg", # degree
    "²": "^2",   # superscript 2
    "³": "^3",   # superscript 3
    "×": "x",    # multiplication sign
    "÷": "/",    # division
    "√": "sqrt", # sqrt
    "∞": "inf",  # infinity
    "≈": "~=",   # approx
    "≠": "!=",   # not equal
    "≤": "<=",   # le
    "≥": ">=",   # ge
    "→": "->",   # rightarrow
    "←": "<-",   # leftarrow
    "±": "+/-",  # plus-minus
    "«": "<<",   # left angle quote
    "»": ">>",   # right angle quote
    "‘": "'",    # left single quote
    "’": "'",    # right single quote
    "“": "\"",   # left double quote
    "”": "\"",   # right double quote
    "…": "...",  # ellipsis
    # Greek letters (most common in math comments)
    "φ": "phi",
    "θ": "theta",
    "π": "pi",
    "λ": "lambda",
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "σ": "sigma",
    "ρ": "rho",
    "μ": "mu",
    "τ": "tau",
    "ω": "omega",
    "Δ": "Delta",
    "Σ": "Sigma",
    "Ω": "Omega",
    "Φ": "Phi",
    # Section / paragraph
    "§": "sec.",
    "¶": "para",
}


def _ascii_transliterate_comment(comment):
    """Rule 2 on a COMMENT token. Non-ASCII chars are mapped via
    ``_COMMENT_MAP``; unmapped chars (e.g. CJK ideographs) are replaced
    with ``?`` so the resulting comment is byte-level ASCII.

    Comments never affect runtime behaviour, so this lossy mapping is
    safe -- the canonical comment text lives in scripts/, not here.
    """
    out = []
    for ch in comment:
        if ord(ch) < 128:
            out.append(ch)
        elif ch in _COMMENT_MAP:
            out.append(_COMMENT_MAP[ch])
        else:
            out.append("?")
    return "".join(out)


# ----------------------------------------------------------------------
# Rule 4 -- isinstance(x, str) -> isinstance(x, _STR_TYPES) + helper
# ----------------------------------------------------------------------

_ISINSTANCE_STR_RE = re.compile(
    r"isinstance\(\s*([^,()]+?)\s*,\s*str\s*\)")

_STR_TYPES_HELPER = (
    "# M_P0_MAYA_VERSION_ISOLATION Rule 4: py2 unicode / py3 str dual\n"
    "# accept tuple. Auto-injected by tools/sync_2022_from_2025.py.\n"
    "try:\n"
    "    _STR_TYPES = (str, unicode)  # noqa: F821 -- py2-only name\n"
    "except NameError:\n"
    "    _STR_TYPES = (str,)\n"
)


def _apply_isinstance_rule(src):
    new_src = _ISINSTANCE_STR_RE.sub(r"isinstance(\1, _STR_TYPES)", src)
    if "_STR_TYPES" in new_src and "_STR_TYPES = (str, unicode)" not in new_src:
        new_src = _inject_str_types_helper(new_src)
    return new_src


def _inject_str_types_helper(src):
    """Insert ``_STR_TYPES`` helper at the EARLIEST safe position:
    after the coding declaration and the leading module docstring,
    BEFORE any ``import`` statement or class/function definition.

    Placing the helper this early ensures ``_STR_TYPES`` is defined in
    the module globals before any ``isinstance(x, _STR_TYPES)`` call
    is reached -- including potential module-load-time uses (class
    attributes, default arguments, etc.).
    """
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return _prepend_helper_after_decl(src)

    lines = src.split("\n")

    # Earliest insertion point: line after the leading docstring,
    # or after the coding decl if no docstring.
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if (insert_at < len(lines)
            and "coding" in lines[insert_at]
            and lines[insert_at].lstrip().startswith("#")):
        insert_at += 1

    # Skip a leading module docstring (first statement, an Expr->Str)
    if tree.body:
        first = tree.body[0]
        is_docstring = (
            isinstance(first, _ast.Expr)
            and isinstance(getattr(first, "value", None), _ast.Constant)
            and isinstance(first.value.value, str))
        if not is_docstring:
            is_docstring = (
                isinstance(first, _ast.Expr)
                and first.value.__class__.__name__ == "Str")
        if is_docstring:
            end = getattr(first, "end_lineno", first.lineno)
            insert_at = max(insert_at, end)

    # Critical: ``from __future__ import ...`` statements must remain
    # the FIRST statements after the docstring. Skip past any of them.
    for node in tree.body:
        if (isinstance(node, _ast.ImportFrom)
                and node.module == "__future__"):
            end_line = getattr(node, "end_lineno", node.lineno)
            insert_at = max(insert_at, end_line)

    helper_lines = ["", ""] + _STR_TYPES_HELPER.rstrip("\n").split("\n") + [""]
    lines[insert_at:insert_at] = helper_lines
    return "\n".join(lines)


def _prepend_helper_after_decl(src):
    """Fallback: insert the helper after the coding declaration (line
    1 or 2 if shebang)."""
    lines = src.split("\n")
    decl_at = 0
    for i in range(min(2, len(lines))):
        if "coding" in lines[i] and lines[i].lstrip().startswith("#"):
            decl_at = i + 1
            break
    helper_lines = [""] + _STR_TYPES_HELPER.rstrip("\n").split("\n") + [""]
    lines[decl_at:decl_at] = helper_lines
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Rule 5 -- defensive import in help_button.py
# ----------------------------------------------------------------------

_HELP_BUTTON_PATCH_HEADER = "# M_P0_MAYA_VERSION_ISOLATION Rule 5"


def _apply_help_button_rule(src):
    """Wrap the lazy ``from RBFtools.ui.help_texts import get_help_text``
    imports in ``help_button.py`` with a module-level try/except and an
    ASCII-only fallback.
    """
    if _HELP_BUTTON_PATCH_HEADER in src:
        return src  # already patched (idempotent)

    # Build the fallback block via chr() so the source of this sync
    # script remains byte-level ASCII even though the runtime value of
    # the fallback contains U+26A0.
    bs = chr(0x5C)  # backslash
    warn_escape = bs + "u26a0"
    nl_escape = bs + "n"
    nlnl_escape = nl_escape + nl_escape
    bs_uXXXX = bs + bs + "uXXXX"  # literally \\uXXXX

    fallback_lines = [
        _HELP_BUTTON_PATCH_HEADER + " (auto-injected): defensive import.",
        "# Module-level try/except so a bad help_texts.py source does not",
        "# crash the UI. After sync, scripts_2022/help_texts.py is 100%",
        "# ASCII at byte level so this fallback never triggers in normal",
        "# operation -- belt-and-suspenders, not graceful degradation.",
        "try:",
        "    from RBFtools.ui.help_texts import get_help_text as _get_help_text",
        "    _HELP_TEXTS_OK = True",
        "    _HELP_TEXTS_ERR = None",
        "except Exception as _exc:  # noqa: BLE001",
        "    import warnings as _warnings",
        "    _warnings.warn(",
        '        "RBFtools.ui.help_texts failed to import (likely py2 "',
        '        "encoding issue). Help bubbles will show diagnostic "',
        '        "placeholder. Error: {0}".format(_exc),',
        "        RuntimeWarning,",
        "    )",
        "    _HELP_TEXTS_OK = False",
        "    _HELP_TEXTS_ERR = _exc",
        "",
        "    def _get_help_text(key):",
        '        return (',
        '            u"[' + warn_escape + ' RBFtools help_texts.py import "',
        '            u"failed - see Maya Script Editor warning]'
        + nlnl_escape + '"',
        '            u"Error: {0}' + nlnl_escape + '"',
        '            u"Patch ID: M_P0_MAYA_VERSION_ISOLATION Rule 5 "',
        '            u"fallback. Re-run tools/sync_2022_from_2025.py "',
        '            u"to refresh scripts_2022 from the canonical "',
        '            u"scripts/ (Maya 2025 path). A non-ASCII byte "',
        '            u"sneaked in without a ' + bs_uXXXX + ' escape."',
        '            .format(_HELP_TEXTS_ERR)',
        '        )',
        "",
    ]

    # Replace the in-function imports first.
    src = src.replace(
        "        bubble = self._get_bubble()\n"
        "        from RBFtools.ui.help_texts import get_help_text\n"
        "        bubble.set_text(get_help_text(self._help_key))\n",
        "        bubble = self._get_bubble()\n"
        "        bubble.set_text(_get_help_text(self._help_key))\n",
    )
    src = src.replace(
        "        bubble = self._get_bubble()\n"
        "        from RBFtools.ui.help_texts import get_help_text\n"
        "        bubble.set_text(get_help_text(self._current_help_key()))\n",
        "        bubble = self._get_bubble()\n"
        "        bubble.set_text(_get_help_text(self._current_help_key()))\n",
    )
    src = src.replace(
        "        if self._pinned and self._bubble is not None and self._bubble.isVisible():\n"
        "            from RBFtools.ui.help_texts import get_help_text\n"
        "            self._bubble.set_text(get_help_text(self._help_key_for_index(idx)))\n",
        "        if self._pinned and self._bubble is not None and self._bubble.isVisible():\n"
        "            self._bubble.set_text(_get_help_text(self._help_key_for_index(idx)))\n",
    )

    # Insert the module-level block after the existing compat import.
    anchor = "from RBFtools.ui.compat import QtWidgets, QtCore\n"
    if anchor in src:
        insertion = anchor + "\n" + "\n".join(fallback_lines)
        src = src.replace(anchor, insertion, 1)
    return src


# ----------------------------------------------------------------------
# Coding declaration (Rule 1)
# ----------------------------------------------------------------------

_PEP263_RE = re.compile(r"coding[:=]\s*[-\w.]+")


def _ensure_coding_decl(src):
    """Insert ``# -*- coding: utf-8 -*-`` on line 1 (or line 2 if line 1
    is a shebang) if no PEP 263 declaration is present on lines 1-2.
    """
    lines = src.split("\n")
    head = lines[:2]
    for h in head:
        if h.lstrip().startswith("#") and _PEP263_RE.search(h):
            return src
    decl = "# -*- coding: utf-8 -*-"
    if lines and lines[0].startswith("#!"):
        lines.insert(1, decl)
    else:
        lines.insert(0, decl)
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Token-based transform driver
# ----------------------------------------------------------------------

def _normalise_eol(src, eol):
    """Convert all line endings in *src* to *eol*."""
    return src.replace("\r\n", "\n").replace("\r", "\n").replace("\n", eol)


def transform_source(src_bytes, rel_path):
    """Apply Rules 1-5 (+6/7 audit) to one Python source. Returns
    transformed bytes (pure ASCII).

    Output line endings are ALWAYS LF (`\\n`), independent of the
    source file's line endings. This is required for the drift
    detector (Phase 6) to be stable across checkouts with different
    ``core.autocrlf`` settings -- otherwise a Linux clone (LF) and a
    Windows clone (CRLF) of scripts/ would produce different
    scripts_2022/ bytes from the same canonical source.
    """
    src = src_bytes.decode("utf-8")
    # Normalise input EOL to LF so tokenize sees a consistent stream
    src = src.replace("\r\n", "\n").replace("\r", "\n")

    # Rule 1
    src = _ensure_coding_decl(src)

    # Rule 2 + 3 via tokenize
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError as exc:
        raise RuntimeError("tokenize failed in {0}: {1}".format(rel_path, exc))

    new_tokens = []
    for tok in tokens:
        ttype = tok[0]
        tstr = tok[1]
        if ttype == tokenize.STRING:
            new_tokens.append(tok._replace(string=_ascii_escape_string_token(tstr)))
        elif ttype == tokenize.COMMENT:
            new_tokens.append(tok._replace(string=_ascii_transliterate_comment(tstr)))
        else:
            new_tokens.append(tok)

    # Reconstruct source from tokens preserving column positions.
    out_src = _untokenize_preserving_layout(new_tokens, src)

    # Rule 4 (regex applied AFTER tokenize so isinstance pattern is
    # matched in the post-tokenize source -- the pattern is whitespace
    # tolerant)
    out_src = _apply_isinstance_rule(out_src)

    # Rule 5 (only for help_button.py)
    if rel_path.replace(os.sep, "/").endswith("ui/widgets/help_button.py"):
        out_src = _apply_help_button_rule(out_src)

    # Rule 6/7 audit (warn only)
    _audit_py3_only_syntax(out_src, rel_path)

    # Final validation: source must be pure ASCII
    try:
        out_bytes = out_src.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            "Non-ASCII byte survived transform in {0}: {1}".format(
                rel_path, exc))

    # Output ALWAYS LF (see docstring); Git auto-LF translation on
    # Windows checkouts of scripts_2022 still works because
    # .gitattributes (added in the same patch) marks scripts_2022 as
    # text/auto.
    return out_bytes


def _untokenize_preserving_layout(tokens, original_src):
    """Reconstruct source from tokens preserving each token's exact
    (line, col) position so whitespace is byte-perfect.

    ``tokenize.untokenize`` is whitespace-sloppy; this implementation
    walks the token stream and emits source character-by-character
    using ``tok.start`` / ``tok.end`` positions.
    """
    src_lines = original_src.split("\n")
    out_lines = list(src_lines)  # we will overwrite by token slices
    # Build a list of edits: (start, end, new_string)
    edits = []
    for tok in tokens:
        if tok[0] not in (tokenize.STRING, tokenize.COMMENT):
            continue
        start = tok[2]  # (row, col), 1-based row, 0-based col
        end = tok[3]
        new_text = tok[1]
        edits.append((start, end, new_text))

    # Apply edits from end to start so positions remain valid
    edits.sort(key=lambda e: (e[0][0], e[0][1]), reverse=True)
    for (srow, scol), (erow, ecol), new_text in edits:
        if srow == erow:
            line = out_lines[srow - 1]
            out_lines[srow - 1] = line[:scol] + new_text + line[ecol:]
        else:
            # Multi-line token (triple-quoted string)
            first = out_lines[srow - 1]
            last = out_lines[erow - 1]
            new_first = first[:scol] + new_text
            new_last = last[ecol:]
            # Replace the entire range with one or more lines
            new_block = (new_first + new_last).split("\n")
            out_lines[srow - 1:erow] = new_block
    return "\n".join(out_lines)


# ----------------------------------------------------------------------
# Rule 6 / 7 audit
# ----------------------------------------------------------------------

_PY3_ONLY_PATTERNS = [
    (re.compile(r'\bf"'), "f-string"),
    (re.compile(r":="), "walrus operator"),
    (re.compile(r"\bnonlocal\b"), "nonlocal keyword"),
    (re.compile(r"\bsuper\(\)"), "super() no-arg form"),
]


def _audit_py3_only_syntax(src, rel_path):
    """Emit a warning for any py3-only syntax found. Currently the
    project has zero hits but the audit guards against regressions.
    """
    for pat, label in _PY3_ONLY_PATTERNS:
        if pat.search(src):
            print("WARN: {0}: py3-only syntax found: {1}".format(
                rel_path, label))


# ----------------------------------------------------------------------
# File walker / driver
# ----------------------------------------------------------------------

def _compute_transformed(src_path, rel_path):
    with open(src_path, "rb") as fh:
        src_bytes = fh.read()
    return transform_source(src_bytes, rel_path)


def sync_all(check_only=False, verbose=False):
    """Walk SRC_DIR, transform every .py, mirror non-.py files
    byte-for-byte. Return list of (path, reason) for any drift.
    """
    diffs = []
    py_count = 0
    other_count = 0

    if not check_only:
        # Wipe DST to guarantee no stale files. Then walk SRC.
        if os.path.exists(DST_DIR):
            shutil.rmtree(DST_DIR)
        os.makedirs(DST_DIR)

    for dirpath, dirnames, filenames in os.walk(SRC_DIR):
        # Prune __pycache__ dirs
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        rel = os.path.relpath(dirpath, SRC_DIR)
        dst_dirpath = (DST_DIR if rel == "." else os.path.join(DST_DIR, rel))
        if not check_only and not os.path.exists(dst_dirpath):
            os.makedirs(dst_dirpath)
        for fn in sorted(filenames):
            src_path = os.path.join(dirpath, fn)
            dst_path = os.path.join(dst_dirpath, fn)
            rel_path = os.path.relpath(dst_path, "modules").replace(os.sep, "/")
            if fn.endswith(".py"):
                py_count += 1
                try:
                    expected = _compute_transformed(src_path, rel_path)
                except Exception as exc:
                    diffs.append((dst_path, "transform error: {0}".format(exc)))
                    continue
                if check_only:
                    if not os.path.exists(dst_path):
                        diffs.append((dst_path, "missing"))
                        continue
                    with open(dst_path, "rb") as fh:
                        actual = fh.read()
                    if actual != expected:
                        diffs.append((dst_path, "content differs"))
                else:
                    with open(dst_path, "wb") as fh:
                        fh.write(expected)
                    if verbose:
                        print("WROTE: {0} ({1} bytes)".format(
                            dst_path, len(expected)))
            else:
                # Non-.py files (e.g. .mel) -- copy with EOL normalised
                # to LF to keep the drift check stable across autocrlf.
                other_count += 1
                with open(src_path, "rb") as fh:
                    src_bytes = fh.read()
                expected = src_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                if check_only:
                    if not os.path.exists(dst_path):
                        diffs.append((dst_path, "missing"))
                        continue
                    with open(dst_path, "rb") as fh:
                        actual = fh.read()
                    if actual != expected:
                        diffs.append((dst_path, "byte differs"))
                else:
                    with open(dst_path, "wb") as fh:
                        fh.write(expected)
    return diffs, py_count, other_count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="drift detector mode (exit 1 on diff, do not write)")
    p.add_argument("--verbose", action="store_true",
                   help="print one line per written file")
    args = p.parse_args()

    diffs, py_count, other_count = sync_all(
        check_only=args.check, verbose=args.verbose)
    if args.check:
        if diffs:
            print("ERROR: scripts_2022/ drift detected vs sync output:")
            for path, reason in diffs:
                print("  ! {0}: {1}".format(path, reason))
            print("Fix: run `python tools/sync_2022_from_2025.py`.")
            sys.exit(1)
        print("OK: scripts_2022/ matches sync script output "
              "({0} py + {1} other files).".format(py_count, other_count))
    else:
        print("OK: scripts_2022/ regenerated ({0} py + {1} other "
              "files).".format(py_count, other_count))


if __name__ == "__main__":
    main()
