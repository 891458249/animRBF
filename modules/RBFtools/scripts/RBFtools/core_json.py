# -*- coding: utf-8 -*-
"""JSON I/O utilities for v5 RBFtools schema (Milestone 3.0).

Lives in its own module because:
  * core.py is already 1860+ lines (M2.3 made it heavy)
  * I/O serialization is logically distinct from node DG ops
  * M3.3 will extend this file with export_solver_to_json /
    import_solver_from_json (~200+ lines), which would push core.py
    past 2000 lines if appended there

============================================================
SCHEMA_VERSION IMMUTABILITY CONTRACT (v5 addendum §M3.0)
============================================================
The string ``SCHEMA_VERSION`` defined below is a permanent invariant.
Changing it BREAKS downstream engine integration's compatibility
gate — engine-side runtime components use this string to decide
whether they can consume an exported JSON.

Any future schema evolution MUST:

  1. Introduce a NEW version string (e.g. "rbftools.v5.m3.1" or
     "rbftools.v6") — never modify the existing string while
     leaving field semantics drifting underneath it.
  2. Extend the reader to support BOTH the old and new versions
     (multi-version dispatcher in read_json_with_schema_check).
  3. Document the change in a new addendum sub-section
     ``§M3.x-extension-YYYYMMDD``.

Three-layer guard (addendum §M3.0):
  - This source comment   (you are reading layer 1)
  - The contract paragraph in addendum §M3.0
  - The permanent test ``test_schema_version_unchanged_M3_0``
    in tests/test_m3_0_infrastructure.py
"""

from __future__ import absolute_import

import json
import os
import tempfile


# === Permanent invariant (addendum §M3.0 — DO NOT MODIFY) ===
# Changing this string breaks downstream engine integration's
# compatibility gate. Any schema evolution MUST introduce a new
# version string and a multi-version reader. See the module
# docstring above and addendum §M3.0 Schema Version Immutability
# Contract before making any change.
SCHEMA_VERSION = "rbftools.v5.m3"


class SchemaVersionError(Exception):
    """Raised by :func:`read_json_with_schema_check` when the file's
    ``schema_version`` field does not equal :data:`SCHEMA_VERSION`.

    M3.3 will extend the reader with multi-version dispatch; for M3.0
    the contract is strict equality.
    """


def atomic_write_json(path, data):
    """Write *data* to *path* atomically.

    Strategy: stage to a temp file in the **same directory**, then
    ``os.replace`` to the final path. This eliminates partial-write
    visibility (a crash mid-write leaves either the old file or the
    new file, never a half-written one) — important for engine-side
    consumers that poll the file or react to filesystem watchers.

    Same-directory staging is required because ``os.replace`` is
    atomic only within a single filesystem; a cross-mount tempdir
    would degrade to copy + unlink with a brief partial state.

    Parameters
    ----------
    path : str
        Final destination filesystem path.
    data : Any (JSON-serialisable)
        Object passed to :func:`json.dump`. Must include a
        ``"schema_version"`` field set to :data:`SCHEMA_VERSION` if
        it is meant to be readable by :func:`read_json_with_schema_check`.
    """
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".rbftools_", suffix=".json.tmp",
                                dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2,
                      sort_keys=False)
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup of the staged temp file.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json_with_schema_check(path):
    """Read JSON from *path* and verify ``schema_version`` matches.

    Parameters
    ----------
    path : str
        Filesystem path to a JSON document previously written by
        :func:`atomic_write_json`.

    Returns
    -------
    dict
        The parsed JSON document.

    Raises
    ------
    SchemaVersionError
        If the file's ``schema_version`` field is missing or differs
        from :data:`SCHEMA_VERSION`. M3.3 may extend this with multi-
        version dispatch; for M3.0 strict equality is the contract.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    got = data.get("schema_version") if isinstance(data, dict) else None
    if got != SCHEMA_VERSION:
        raise SchemaVersionError(
            "Schema mismatch: expected {!r}, got {!r}".format(
                SCHEMA_VERSION, got))
    return data
