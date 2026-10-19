
import json
from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GLOSSARY_PATH = (
    PROJECT_ROOT / "data" / "knowledge" / "domain_lexicon.json"
)



def _load_document() -> dict:
    """Load legacy or versioned glossary data."""

    with GLOSSARY_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Glossary must be a JSON object")

    # Support the original flat JSON format.
    if "terms" not in data:
        data = {
            "version": 1,
            "updated_at": None,
            "updated_by": None,
            "terms": data,
        }

    terms = data["terms"]

    if not isinstance(terms, dict) or any(
        not isinstance(term, str)
        or not isinstance(definition, str)
        or not term.strip()
        or not definition.strip()
        for term, definition in terms.items()
    ):
        raise ValueError("Invalid terminology entries")

    if (
        type(data.get("version")) is not int
        or data["version"] < 1
    ):
        raise ValueError("Invalid glossary version")

    return data


def get_terms() -> dict[str, str]:
    """Return the latest terminology definitions."""

    return dict(_load_document()["terms"])


def update_term(
    term: str,
    definition: str,
    updated_by: str,
) -> int:
    """Add or update a term and increment glossary version."""

    if not all(
        isinstance(value, str) and value.strip()
        for value in (term, definition, updated_by)
    ):
        raise ValueError("Term, definition and editor are required")

    term = term.strip()
    definition = definition.strip()

    data = _load_document()

    # No change means no new version.
    if data["terms"].get(term) == definition:
        return data["version"]

    data["terms"][term] = definition
    data["version"] += 1
    data["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()
    data["updated_by"] = updated_by.strip()

    # Write to a temporary file before replacing the original.
    temporary = GLOSSARY_PATH.with_name(
        GLOSSARY_PATH.name + ".tmp"
    )

    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(GLOSSARY_PATH)

    return data["version"]


def delete_term(term: str, updated_by: str) -> int:
    """Delete an existing term and increment glossary version."""

    if not all(
        isinstance(value, str) and value.strip()
        for value in (term, updated_by)
    ):
        raise ValueError("Term and editor are required")

    term = term.strip()
    data = _load_document()

    if term not in data["terms"]:
        raise KeyError(f"Term not found: {term}")

    del data["terms"][term]

    data["version"] += 1
    data["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()
    data["updated_by"] = updated_by.strip()

    temporary = GLOSSARY_PATH.with_name(
        GLOSSARY_PATH.name + ".tmp"
    )

    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(GLOSSARY_PATH)

    return data["version"]
