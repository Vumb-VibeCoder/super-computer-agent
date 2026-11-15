"""Public-side license verification for the proprietary canvas/pixel_grid
binaries (see PROPRIETARY_EULA.md).

This module ships with the package. It only ever holds the PUBLIC key —
never the private signing key, which lives exclusively in
licensor-tools/ (not part of this repo's public distribution).
"""
from .verify import (
    LicenseError,
    LicenseInfo,
    check_license,
    license_slot,
)
from .machine_id import get_machine_id

__all__ = [
    "LicenseError",
    "LicenseInfo",
    "check_license",
    "license_slot",
    "get_machine_id",
]
