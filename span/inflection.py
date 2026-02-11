"""Inflection point detection using 5-point monotonicity validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InflectionType(Enum):
    NORMAL = "normal"
    DOWN_TO_UP = "down->up"
    UP_TO_DOWN = "up->down"


@dataclass
class InflectionResult:
    """Result of inflection analysis for the entire dataset."""

    labels: list[InflectionType]  # One label per data point


def detect_inflections(flux: list[float]) -> InflectionResult:
    """Detect validated inflection points in flux data.

    Uses a 5-point monotonicity check: for a direction change at point P,
    the reversal is only valid if the 2 points before P continue monotonically
    in the old direction AND the 2 points after P continue monotonically in
    the new direction.

    Args:
        flux: List of flux values.

    Returns:
        InflectionResult with a label for each data point.
    """
    n = len(flux)
    labels = [InflectionType.NORMAL] * n

    if n < 5:
        return InflectionResult(labels=labels)

    # Determine initial direction
    prev_direction = None  # "up" or "down"
    for i in range(1, n):
        if flux[i] > flux[i - 1]:
            prev_direction = "up"
            break
        elif flux[i] < flux[i - 1]:
            prev_direction = "down"
            break

    if prev_direction is None:
        return InflectionResult(labels=labels)

    # Scan for direction changes
    for i in range(2, n):
        if flux[i] > flux[i - 1]:
            current_direction = "up"
        elif flux[i] < flux[i - 1]:
            current_direction = "down"
        else:
            continue

        if current_direction != prev_direction:
            # Candidate inflection at point i-1
            p = i - 1

            if prev_direction == "down" and current_direction == "up":
                # Down-to-up: verify 2 before were descending, 2 after ascending
                if (
                    p >= 2
                    and p + 2 < n
                    and flux[p] < flux[p + 1]
                    and flux[p + 1] < flux[p + 2]
                    and flux[p] < flux[p - 1]
                    and flux[p - 1] < flux[p - 2]
                ):
                    labels[p] = InflectionType.DOWN_TO_UP

            elif prev_direction == "up" and current_direction == "down":
                # Up-to-down: verify 2 before were ascending, 2 after descending
                if (
                    p >= 2
                    and p + 2 < n
                    and flux[p] > flux[p + 1]
                    and flux[p + 1] > flux[p + 2]
                    and flux[p] > flux[p - 1]
                    and flux[p - 1] > flux[p - 2]
                ):
                    labels[p] = InflectionType.UP_TO_DOWN

            prev_direction = current_direction

    return InflectionResult(labels=labels)


def get_inflection_points(
    flux: list[float],
    labels: list[InflectionType],
    filter_type: InflectionType | None = None,
) -> list[tuple[int, float, InflectionType]]:
    """Extract inflection points as a list of (index, flux_value, type).

    Args:
        flux: List of flux values.
        labels: Labels from detect_inflections.
        filter_type: If set, only return points of this type.

    Returns:
        List of (point_index, flux_value, inflection_type) tuples.
    """
    points = []
    for i, label in enumerate(labels):
        if label == InflectionType.NORMAL:
            continue
        if filter_type is not None and label != filter_type:
            continue
        points.append((i, flux[i], label))
    return points
