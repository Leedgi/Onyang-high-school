from core.models import CautionRecord, ClassifiedIngredient
from core.normalize import normalize_key


def lookup_cautions(
    rows: tuple[ClassifiedIngredient, ...], records: list[CautionRecord],
) -> dict[str, tuple[CautionRecord, ...]]:
    return {
        row.canonical_name: tuple(record for record in records if normalize_key(record.name) == normalize_key(row.canonical_name))
        for row in rows
    }
