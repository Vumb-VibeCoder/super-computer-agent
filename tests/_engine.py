"""Skip helpers for tests that need the closed-source canvas / pixel_grid engines.

The compiled .pyd files are built for one Python version only and are gated by
a license key, so a plain CI runner can't load them. These helpers let those
tests skip there while everything else (coordination, server, uia,
screenshot) keeps running.
"""
import importlib.util
import sys

import pytest


def engine_status(*modules):
    """Return None when every compiled module can load here, else the reason why not."""
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    for name in modules:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            return f"{name} has no build for Python {py}"
    from super_computer_agent.licensing import LicenseError, check_license
    try:
        check_license()
    except LicenseError as e:
        return f"proprietary engine needs a license key: {e}"
    return None


def require_engine(*modules, module_level=True):
    """Skip unless every compiled module can load here.

    Call it at the top of a test module (skips the whole module), or inside a
    fixture with module_level=False (skips only the tests using that fixture).
    """
    reason = engine_status(*modules)
    if reason:
        pytest.skip(reason, allow_module_level=module_level)
