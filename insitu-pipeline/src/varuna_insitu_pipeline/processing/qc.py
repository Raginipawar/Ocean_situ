"""
Oceanographic Quality Control (QC) flag filtering.

Implements standard IOC/WMO and Argo quality control flag standards:
- 1: Good data
- 2: Probably good data
- 3: Bad data that are potentially correctable
- 4: Bad data (discard)
- 9: Missing value
"""
from __future__ import annotations

from collections.abc import Collection
from typing import Any

DEFAULT_ALLOWED_QC_FLAGS = (1, 2)


def parse_qc_flag(raw_flag: Any) -> int | None:
    """
    Parse a raw QC flag into an integer.
    Supports integers, integer strings ("1", "2"), and byte characters (b'1').
    Returns None if unparseable or missing.
    """
    if raw_flag is None:
        return None
    if isinstance(raw_flag, (bytes, bytearray)):
        try:
            raw_flag = raw_flag.decode("ascii")
        except UnicodeDecodeError:
            return None
    if isinstance(raw_flag, str):
        raw_flag = raw_flag.strip()
        if not raw_flag or raw_flag in (" ", "\x00"):
            return None
    try:
        return int(raw_flag)
    except (ValueError, TypeError):
        return None


def is_qc_acceptable(raw_flag: Any, allowed_flags: Collection[int] = DEFAULT_ALLOWED_QC_FLAGS) -> bool:
    """
    Check if a raw QC flag is within the acceptable list.
    If flag is missing (None), returns True by default (unless strictly invalid).
    """
    code = parse_qc_flag(raw_flag)
    if code is None:
        # If no QC flag was provided by the instrument, don't drop on QC alone
        return True
    return code in allowed_flags
