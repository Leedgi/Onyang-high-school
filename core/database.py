"""사용자 서비스의 실자료 CSV를 읽는다. 가상 자료 모드는 제공하지 않는다."""
import csv
import json
import hashlib
from functools import lru_cache
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from core.models import CautionRecord, IngredientRecord, ORIGINS, UNCERTAINTIES
from core.normalize import normalize_key

ROOT = Path(__file__).resolve().parents[1]


def safe_source_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https" and parsed.hostname and "." in parsed.hostname
            and not parsed.username and not parsed.password
            and not any(c.isspace() for c in value)
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


def validate_evidence(url: str, checked_on: str) -> None:
    if not safe_source_url(url):
        raise ValueError("근거 URL은 사용자 정보가 없는 HTTPS 주소여야 합니다.")
    try:
        checked = date.fromisoformat(checked_on)
    except ValueError as exc:
        raise ValueError("근거 확인 날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc
    if checked > date.today():
        raise ValueError("근거 확인 날짜를 미래로 기록할 수 없습니다.")


def read_csv(path: Path, fields: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not fields.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"{path.name}: CSV 열 이름이 자료 규격과 다릅니다.")
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"{path.name}: CSV 열 개수를 확인해 주세요.")
    return rows


class IngredientDatabase:
    def __init__(self, records: list[IngredientRecord], dataset_kind: str = "real", registry_count: int = 0):
        if dataset_kind != "real":
            raise ValueError("지원하지 않는 자료 모드입니다.")
        self.dataset_kind = dataset_kind
        self.records = tuple(records)
        self.registry_count = registry_count
        self.curated_count = len(records) - registry_count
        self.origin_counts = {origin: sum(record.origin == origin for record in records) for origin in ORIGINS}
        self.index: dict[str, IngredientRecord] = {}
        checked_evidence = set()
        for record in records:
            if not record.name.strip() or record.origin not in ORIGINS or not record.reason.strip():
                raise ValueError("성분명·유래·근거 설명을 확인해 주세요.")
            if record.origin == "확인 필요" and record.uncertainty_reason not in UNCERTAINTIES:
                raise ValueError("확인 필요 성분에는 원인 코드가 필요합니다.")
            if record.origin != "확인 필요" and record.uncertainty_reason:
                raise ValueError("확정 유래와 확인 필요 원인 코드가 충돌합니다.")
            if dataset_kind == "real":
                if record.source_url or record.checked_on or record.origin != "확인 필요":
                    pair = (record.source_url, record.checked_on)
                    if pair not in checked_evidence:
                        validate_evidence(*pair)
                        checked_evidence.add(pair)
                elif record.uncertainty_reason != "evidence_insufficient":
                    raise ValueError("출처가 없는 실자료는 근거 자료 부족으로 남겨야 합니다.")
            for name in (record.name, *record.aliases):
                key = normalize_key(name)
                if not key or (key in self.index and self.index[key] != record):
                    raise ValueError(f"중복되거나 충돌하는 정식명·별칭: {name}")
                self.index[key] = record
        content = [(r.name, r.aliases, r.origin, r.reason, r.functions, r.source_url, r.checked_on, r.uncertainty_reason) for r in records]
        self.fingerprint = hashlib.sha256(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def find(self, name: str) -> IngredientRecord | None:
        return self.index.get(normalize_key(name))


def load_ingredients(root: Path = ROOT) -> IngredientDatabase:
    root = root.resolve()
    paths = [root / "data/ingredients.csv"]
    if (root / "data/ingredient_names.csv").exists():
        paths.extend([root / "data/ingredient_names.csv", root / "data/sources.json"])
    stamp = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)
    return _load_ingredients_cached(root, stamp)


@lru_cache(maxsize=4)
def _load_ingredients_cached(root: Path, stamp: tuple) -> IngredientDatabase:
    # 파일이 바뀌면 다른 캐시 키를 사용한다. 사용자 입력·분석 결과는 캐시하지 않는다.
    entries = read_csv(root / "data/ingredients.csv", {
        "name", "aliases", "origin", "reason", "functions", "source_url", "checked_on", "uncertainty_reason",
    })
    records = []
    for entry in entries:
        entry = dict(entry)
        for key in ("aliases", "functions"):
            value = entry.get(key, [])
            entry[key] = tuple(filter(None, value.split("|"))) if isinstance(value, str) else tuple(value)
        records.append(IngredientRecord(**entry))
    registry_count = 0
    registry_path = root / "data/ingredient_names.csv"
    if registry_path.exists():
        try:
            manifest = json.loads((root / "data/sources.json").read_text(encoding="utf-8"))
            source_url = manifest["sources"]["identifiers"]["source_url"]
            checked_on = manifest["checked_on"]
        except (KeyError, TypeError) as exc:
            raise ValueError("sources.json의 식별자 출처·검토일을 확인해 주세요.") from exc
        known = {normalize_key(name) for record in records for name in (record.name, *record.aliases)}
        for entry in read_csv(registry_path, {"name", "cosing_id", "cas_no", "ec_no", "pubchem_id"}):
            name = entry["name"].strip()
            key = normalize_key(name)
            if not key or key in known:
                raise ValueError(f"식별자 사전의 중복·빈 이름을 확인해 주세요: {name}")
            known.add(key)
            records.append(IngredientRecord(
                name, (), "확인 필요",
                "BEAUTEE 공개 INCI 식별자 사전의 이름입니다. 이름·식별자만 제공하는 자료여서 제조 원료 유래·안전성·사용 허용은 확인되지 않았습니다.",
                source_url=source_url, checked_on=checked_on, uncertainty_reason="evidence_insufficient",
            ))
            registry_count += 1
    return IngredientDatabase(records, "real", registry_count)


def load_cautions(root: Path = ROOT) -> list[CautionRecord]:
    fields = set(CautionRecord.__dataclass_fields__)
    rows = read_csv(root / "data/cautions.csv", fields)
    records = []
    for row in rows:
        if not row["name"].strip() or not row["reason"].strip():
            raise ValueError("주의 정보에는 성분명과 주의 이유가 필요합니다.")
        validate_evidence(row["source_url"], row["checked_on"])
        records.append(CautionRecord(**row))
    return records
