"""Shared helpers for the report layer.

Small, pure utilities reused by the PDF, Excel, and JSON report writers:
output-path resolution, consistency checking between a well and its assessment,
trace flattening for tabular export, and value formatting.

This module contains no business logic; it only shapes already-computed results
for presentation and persistence.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from lwra.models.well import WellData
from lwra.services.pipeline import WellAssessment

__all__ = [
    "DISCLAIMER",
    "resolve_output_path",
    "check_consistency",
    "flatten",
    "fmt",
]

# Standard non-compliance disclaimer reproduced on every report artefact.
DISCLAIMER: str = (
    "Methodology is inspired by API RP 90, NORSOK D-010, ISO 27914, and "
    "well-barrier and risk-based principles. This tool does not claim official "
    "compliance with any standard. Results are advisory and must be reviewed by "
    "a qualified well-integrity engineer before any operational decision."
)


def resolve_output_path(
    output_path: str | Path | None,
    *,
    well_id: str,
    default_dir: str | Path,
    suffix: str,
) -> Path:
    """Resolve and prepare the destination path for a report file.

    If ``output_path`` is given it is used verbatim (its parent created); if it
    names an existing directory, a default filename is placed inside it. When
    ``output_path`` is ``None`` a deterministic filename is generated under
    ``default_dir``.

    Args:
        output_path: Caller-supplied file or directory path, or ``None``.
        well_id: Well identifier used in the generated filename.
        default_dir: Directory used when ``output_path`` is ``None``.
        suffix: File extension including the leading dot (e.g. ``".pdf"``).

    Returns:
        The resolved, parent-created destination :class:`~pathlib.Path`.

    """
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in well_id)
    filename = f"lwra_{safe_id}{suffix}"

    if output_path is None:
        target = Path(default_dir) / filename
    else:
        candidate = Path(output_path)
        if candidate.is_dir() or candidate.suffix == "":
            target = candidate / filename
        else:
            target = candidate

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def check_consistency(well: WellData, assessment: WellAssessment) -> None:
    """Validate that a well and an assessment refer to the same well.

    Args:
        well: The source well data.
        assessment: The assessment to be reported.

    Raises:
        ValueError: If the two ``well_id`` values differ.

    """
    if well.well_id != assessment.well_id:
        raise ValueError(
            "well and assessment refer to different wells "
            f"({well.well_id!r} != {assessment.well_id!r})."
        )


def fmt(value: Any) -> str:
    """Format a scalar value for human-readable presentation.

    Args:
        value: Any scalar (number, enum, date/datetime, bool, None, str).

    Returns:
        A clean string rendering. ``None`` becomes an en dash; floats are
        trimmed to two decimals; enums render as their value.

    """
    if value is None:
        return "\u2013"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def flatten(obj: Any, *, prefix: str = "", sep: str = ".") -> dict[str, Any]:
    """Flatten a nested dict/list structure into dotted-key scalar pairs.

    Used to render a calculation trace as a two-column (key, value) table for
    the Excel ``Calculation Traces`` sheet without losing any information.

    Args:
        obj: The nested structure (typically a calculation trace).
        prefix: Internal recursion prefix; leave as default at the top level.
        sep: Separator between key segments.

    Returns:
        A flat mapping of dotted keys to scalar values, in traversal order.

    """
    flat: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}{sep}{key}" if prefix else str(key)
            flat.update(flatten(value, prefix=new_prefix, sep=sep))
    elif isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            new_prefix = f"{prefix}[{index}]"
            flat.update(flatten(value, prefix=new_prefix, sep=sep))
    else:
        flat[prefix] = obj
    return flat
