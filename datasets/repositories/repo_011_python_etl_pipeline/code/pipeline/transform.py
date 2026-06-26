from datetime import datetime


def normalize_row(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "name": row["name"].strip().title(),
        "amount": float(row.get("amount", 0) or 0),
        "created_at": _parse_date(row.get("created_at", "")),
    }


def _parse_date(value: str) -> str:
    # BUG: only one date format is supported, others raise ValueError.
    return datetime.strptime(value, "%Y-%m-%d").isoformat()


def deduplicate(rows: list[dict]) -> list[dict]:
    seen: set[int] = set()
    unique = []
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        unique.append(row)
    return unique
