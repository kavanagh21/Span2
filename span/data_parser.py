"""Parser for moorFLPI V5 Review CSV export files."""

from __future__ import annotations


def parse_flux_file(filepath: str) -> list[float]:
    """Parse a moorFLPI tab-delimited CSV and return Flux Mean values.

    The file format has 4 header lines followed by tab-delimited data rows.
    Column index 2 is "Flux Mean".

    Args:
        filepath: Path to the CSV file.

    Returns:
        List of Flux Mean values as floats.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file has fewer than 5 lines or data cannot be parsed.
    """
    flux_values: list[float] = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        # Skip 4 header lines
        for i in range(4):
            line = f.readline()
            if not line:
                raise ValueError(
                    f"File has fewer than 4 header lines (ended at line {i + 1})"
                )

        # Read data lines
        for line_num, line in enumerate(f, start=5):
            line = line.strip()
            if not line:
                continue
            columns = line.split("\t")
            if len(columns) < 3:
                continue
            try:
                flux_values.append(float(columns[2]))
            except (ValueError, IndexError):
                continue

    if not flux_values:
        raise ValueError("No valid flux data found in file")

    return flux_values
