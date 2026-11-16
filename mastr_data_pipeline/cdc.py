"""Snapshot-based CDC helpers (pure Python, mirrors dbt int_mastr_unit_cdc rules).

CDC compares consecutive complete snapshots with export_scope = all_statuses.
November 9 (legacy_mixed_filters) is excluded. Change types:

- INSERT: unit appears only in the later snapshot
- UPDATE: unit in both; tracked attributes differ (null-safe)
- DELETE_CANDIDATE: unit appears only in the earlier snapshot
- UNCHANGED: unit in both; tracked attributes equal
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from mastr_data_pipeline.config_loader import EXPORT_SCOPE_ALL_STATUSES

CHANGE_INSERT = "INSERT"
CHANGE_UPDATE = "UPDATE"
CHANGE_DELETE_CANDIDATE = "DELETE_CANDIDATE"
CHANGE_UNCHANGED = "UNCHANGED"

CHANGE_TYPES: frozenset[str] = frozenset(
    {
        CHANGE_INSERT,
        CHANGE_UPDATE,
        CHANGE_DELETE_CANDIDATE,
        CHANGE_UNCHANGED,
    }
)

# Attributes compared for UPDATE detection (English analytical names).
TRACKED_ATTRIBUTES: tuple[str, ...] = (
    "status_code",
    "net_power_kw",
    "storage_capacity_kwh",
    "municipality_id",
)


def values_differ(left: Any, right: Any) -> bool:
    """Null-safe inequality: two NULLs are equal (not a change)."""
    return left != right


def tracked_attributes_differ(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> bool:
    """Return True when any tracked attribute differs (null-safe)."""
    return any(
        values_differ(before.get(name), after.get(name)) for name in TRACKED_ATTRIBUTES
    )


def classify_unit_change(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> str:
    """
    Classify one unit across a consecutive eligible snapshot pair.

    ``before`` / ``after`` are attribute maps (or None if the unit is absent).
    """
    if before is None and after is None:
        raise ValueError("before and after cannot both be None")
    if before is None:
        return CHANGE_INSERT
    if after is None:
        return CHANGE_DELETE_CANDIDATE
    if tracked_attributes_differ(before, after):
        return CHANGE_UPDATE
    return CHANGE_UNCHANGED


def eligible_snapshot_dates(
    snapshot_metadata: Mapping[str, Mapping[str, Any]],
    complete_snapshot_dates: Iterable[str],
) -> list[str]:
    """
    Return sorted CDC-eligible snapshot dates.

    A date is eligible when it is complete and export_scope is all_statuses.
    """
    complete = set(complete_snapshot_dates)
    eligible: list[str] = []
    for snapshot_date in sorted(complete):
        meta = snapshot_metadata.get(snapshot_date)
        if not meta:
            continue
        if meta.get("export_scope") == EXPORT_SCOPE_ALL_STATUSES:
            eligible.append(snapshot_date)
    return eligible


def consecutive_snapshot_pairs(snapshot_dates: Sequence[str]) -> list[tuple[str, str]]:
    """Pair consecutive dates: (d0,d1), (d1,d2), ... Empty if fewer than two dates."""
    ordered = list(snapshot_dates)
    if len(ordered) < 2:
        return []
    return list(zip(ordered, ordered[1:]))


def detect_snapshot_changes(
    from_units: Mapping[str, Mapping[str, Any]],
    to_units: Mapping[str, Mapping[str, Any]],
    *,
    include_unchanged: bool = False,
) -> list[dict[str, Any]]:
    """
    Detect CDC events between two unit maps keyed by unit_id.

    Returns one dict per emitted event with change_type and before_/after_ attrs.
    """
    events: list[dict[str, Any]] = []
    all_ids = sorted(set(from_units) | set(to_units))
    for unit_id in all_ids:
        before = from_units.get(unit_id)
        after = to_units.get(unit_id)
        change_type = classify_unit_change(before, after)
        if change_type == CHANGE_UNCHANGED and not include_unchanged:
            continue
        event: dict[str, Any] = {
            "unit_id": unit_id,
            "change_type": change_type,
            "source_file": (after or before or {}).get("source_file"),
        }
        for name in TRACKED_ATTRIBUTES:
            event[f"before_{name}"] = None if before is None else before.get(name)
            event[f"after_{name}"] = None if after is None else after.get(name)
        events.append(event)
    return events
