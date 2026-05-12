# -*- coding: utf-8 -*-
u"""
RBFtools \u2014 Unified RBF / Vector-Angle deformer toolkit for Maya.

Public API
----------
>>> import RBFtools
>>> RBFtools.show()               # open (or raise) the main window
>>> RBFtools.close()              # programmatically close it
>>> RBFtools.core.create_node()   # headless / batch usage
"""

from __future__ import absolute_import

from RBFtools.constants import TOOL_VERSION as __version__


def show():
    u"""Show the RBF Tools main window (singleton).

    If the window is already open it is raised to the front \u2014
    no duplicate instance is ever created.
    """
    from RBFtools.ui.main_window import show as _show
    return _show()


def close():
    """Close the RBF Tools window if it is open."""
    from RBFtools.ui.main_window import close as _close
    _close()
