"""사용자 서비스의 실자료 CSV를 읽는다. 가상 자료 모드는 제공하지 않는다."""
import csv
import json
import hashlib
from dataclasses import replace
from functools import lru_cache
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from core.models import CautionRecord, IngredientRecord, ORIGINS, UNCERTAINTIES, DETAIL_ORIGINS, INGREDIENT_FIELDS
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
        self.detail_origin_counts = ({origin:sum(r.detail_origin == origin for r in records) for origin in DETAIL_ORIGINS}
                                     if any(r.detail_origin for r in records) else None)
        self.estimated_count = sum(r.detail_is_estimate and r.detail_origin != "확인 필요" for r in records)
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
            if record.detail_origin:
                if record.detail_origin not in DETAIL_ORIGINS or not record.detail_confidence.strip() or not record.detail_reason.strip():
                    raise ValueError("7분류의 범주·검토 수준·근거를 확인해 주세요.")
                if type(record.detail_is_estimate) is not bool or not safe_source_url(record.detail_source_url):
                    raise ValueError("7분류의 추정 표시·출처를 확인해 주세요.")
            for name in (record.name, *record.aliases):
                key = normalize_key(name)
                if not key or (key in self.index and self.index[key] != record):
                    raise ValueError(f"중복되거나 충돌하는 정식명·별칭: {name}")
                self.index[key] = record
        content = [(r.name, r.aliases, r.origin, r.reason, r.functions, r.source_url, r.checked_on, r.uncertainty_reason, r.detail_origin, r.detail_confidence, r.detail_reason, r.detail_source_url, r.detail_is_estimate) for r in records]
        self.fingerprint = hashlib.sha256(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def find(self, name: str) -> IngredientRecord | None:
        return self.index.get(normalize_key(name))


def load_ingredients(root: Path = ROOT) -> IngredientDatabase:
    root = root.resolve()
    paths = [root / "data/ingredients.csv"]
    if (root / "data/ingredient_names.csv").exists():
        paths.extend([root / "data/ingredient_names.csv", root / "data/sources.json"])
    for name in ("cautions.csv", "caution_aliases.csv", "environmental_evidence.csv",
                 "caution_sources.json", "reviewed/caution_review.json", "kcia_sources.json",
                 "kcia_ingredients.csv", "kcia_standard_names.csv", "kcia_import_conflicts.csv",
                 "reviewed/kcia_origin_review.json", "reviewed/kcia_source_input.json",
                 "origin_ingredients.csv", "origin_sources.json", "reviewed/origin_review.json",
                 "reviewed/origin_route_review.json"):
        path = root / "data" / name
        if path.exists():
            paths.append(path)
    for name in ("origin_taxonomy_sources.json", "origin_detail_audit.csv", "origin_additions.csv", "origin_additions_sources.json",
                 "origin_additions_round2.csv", "origin_additions_round2_sources.json", "origin_additions_round3.csv", "origin_additions_round3_sources.json",
                 "origin_additions_round4.csv", "origin_additions_round4_sources.json", "caution_additions.csv", "caution_additions_sources.json"):
        path=root/"data"/name
        if path.exists():paths.append(path)
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
    alias_path = root / "data/caution_aliases.csv"
    if alias_path.exists():
        index = {normalize_key(name): i for i, record in enumerate(records)
                 for name in (record.name, *record.aliases)}
        for entry in read_csv(alias_path, {"alias", "inci", "source_url", "checked_on", "source_cas"}):
            validate_evidence(entry["source_url"], entry["checked_on"])
            alias, target = normalize_key(entry["alias"]), normalize_key(entry["inci"])
            if not alias or target not in index:
                raise ValueError("검증 별칭의 INCI 또는 이름이 없습니다.")
            position = index[target]
            if alias in index:
                if index[alias] != position:
                    raise ValueError("검증 별칭이 다른 성분과 충돌합니다: " + entry["alias"])
                continue
            records[position] = replace(records[position], aliases=(*records[position].aliases, entry["alias"]))
            index[alias] = position
    records, registry_count = apply_kcia_overlay(root, records, registry_count)
    records, registry_count = apply_origin_overlay(root, records, registry_count)
    records = apply_detail_taxonomy(root, records)
    database = IngredientDatabase(records, "real", registry_count)
    components = [database.fingerprint]
    for path_string, _, _ in stamp:
        components.append(hashlib.sha256(Path(path_string).read_bytes()).hexdigest())
    database.fingerprint = hashlib.sha256("|".join(components).encode()).hexdigest()
    return database


def apply_kcia_overlay(root: Path, records: list[IngredientRecord], registry_count: int):
    """기존 CSV → 검증한 선택적 확장 → 같은 자료형. 누락·충돌은 실패 처리."""
    data = root / "data"
    path = data / "kcia_sources.json"
    if not path.exists():
        if (data / "kcia_ingredients.csv").exists():
            raise ValueError("KCIA 확장 자료의 출처 집계가 없습니다.")
        return records, registry_count
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["format_version"] != 1:
            raise ValueError("지원하지 않는 KCIA 확장 자료 버전입니다.")
        for name in ("ingredients.csv", "ingredient_names.csv", "sources.json"):
            if hashlib.sha256((data / name).read_bytes()).hexdigest() != manifest["base_files"][name]:
                raise ValueError("KCIA 확장 자료의 기본 DB가 바뀌었습니다. 자료를 재검토·재생성해 주세요.")
        for name in ("kcia_ingredients.csv", "kcia_standard_names.csv", "kcia_import_conflicts.csv",
                     "reviewed/kcia_origin_review.json", "reviewed/kcia_source_input.json"):
            if hashlib.sha256((data / name).read_bytes()).hexdigest() != manifest["files"][name]:
                raise ValueError("KCIA 자료 체크섬이 일치하지 않습니다. 검토 입력과 생성물을 확인해 주세요.")
        name_only = set(range(len(records) - registry_count, len(records)))
        positions = {normalize_key(r.name): i for i, r in enumerate(records)}
        for entry in read_csv(data / "kcia_ingredients.csv", INGREDIENT_FIELDS):
            entry = dict(entry)
            for key in ("aliases", "functions"):
                entry[key] = tuple(filter(None, entry[key].split("|")))
            record = IngredientRecord(**entry)
            key = normalize_key(record.name)
            position = positions.get(key)
            if position is None:
                position = len(records)
                positions[key] = position
                records.append(record)
                name_only.add(position)
            else:
                records[position] = record
            if record.uncertainty_reason != "evidence_insufficient":
                name_only.discard(position)
        if (len(records) != manifest["merged_records"] or len(name_only) != manifest["merged_registry_count"]):
            raise ValueError("KCIA 확장 자료의 병합 집계가 다릅니다. 기존 자료부터 재검토해 주세요.")
        return records, len(name_only)
    except (KeyError, TypeError) as exc:
        raise ValueError("KCIA 확장 자료의 출처 집계를 확인해 주세요.") from exc


def apply_origin_overlay(root: Path, records: list[IngredientRecord], registry_count: int):
    """검토 입력/기본 DB 일치 → 기존 확인 필요만 보완 → 같은 규격. 오류는 중단."""
    data = root / "data"
    path = data / "origin_sources.json"
    if not path.exists():
        if (data / "origin_ingredients.csv").exists():
            raise ValueError("유래 확장 자료의 출처 집계가 없습니다.")
        return records, registry_count
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["format_version"] != 1:
            raise ValueError("지원하지 않는 유래 자료 버전입니다.")
        for group, names in (
            ("base_files", ("ingredients.csv", "ingredient_names.csv", "sources.json", "kcia_sources.json")),
            ("files", ("origin_ingredients.csv", "reviewed/origin_review.json", "reviewed/origin_route_review.json")),
        ):
            for name in names:
                if hashlib.sha256((data / name).read_bytes()).hexdigest() != manifest[group][name]:
                    raise ValueError("유래 자료 체크섬이 일치하지 않습니다. 기본 자료와 검토 입력을 확인해 주세요.")
        positions = {normalize_key(r.name): i for i, r in enumerate(records)}
        seen = set()
        for entry in read_csv(data / "origin_ingredients.csv", INGREDIENT_FIELDS):
            entry = dict(entry)
            for key in ("aliases", "functions"):
                entry[key] = tuple(filter(None, entry[key].split("|")))
            record = IngredientRecord(**entry)
            position = positions.get(normalize_key(record.name))
            if position is None or position in seen:
                raise ValueError("유래 확장의 정식명 누락·중복을 확인해 주세요.")
            seen.add(position)
            previous = records[position]
            if previous.origin != "확인 필요" or record.aliases != previous.aliases:
                raise ValueError("유래 확장은 기존 확인 필요 성분만 보완하며 별칭을 변경할 수 없습니다.")
            if previous.uncertainty_reason == "evidence_insufficient":
                registry_count -= 1
            records[position] = record
        if (len(seen) != manifest["overlay_records"] or len(records) != manifest["merged_records"]
                or registry_count != manifest["merged_registry_count"]
                or {origin: sum(r.origin == origin for r in records) for origin in ORIGINS} != manifest["merged_origin_counts"]):
            raise ValueError("유래 자료의 병합 집계가 다릅니다.")
        return records, registry_count
    except (KeyError, TypeError) as exc:
        raise ValueError("유래 확장의 출처 집계를 확인해 주세요.") from exc


def load_cautions(root: Path = ROOT) -> list[CautionRecord]:
    manifest_path = root / "data/caution_sources.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name in ("cautions.csv", "caution_aliases.csv", "environmental_evidence.csv"):
                actual = hashlib.sha256((root / "data" / name).read_bytes()).hexdigest()
                if actual != manifest["files"][name]:
                    raise ValueError("주의 자료 체크섬이 일치하지 않습니다. 검토 입력과 생성물을 확인해 주세요.")
        except (KeyError, TypeError) as exc:
            raise ValueError("주의 자료의 출처 집계를 확인해 주세요.") from exc
    fields = set(CautionRecord.__dataclass_fields__)
    rows = read_csv(root / "data/cautions.csv", fields)
    records = []
    for row in rows:
        if not row["name"].strip() or not row["reason"].strip():
            raise ValueError("주의 정보에는 성분명과 주의 이유가 필요합니다.")
        validate_evidence(row["source_url"], row["checked_on"])
        records.append(CautionRecord(**row))
    path=root/"data/caution_additions.csv"
    if path.exists():
        metadata_path=root/"data/caution_additions_sources.json"
        if not metadata_path.exists():raise ValueError("추가 주의 자료 출처 집계가 없습니다.")
        metadata=json.loads(metadata_path.read_text(encoding="utf-8"))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata["sha256"]:raise ValueError("추가 주의 자료 체크섬 불일치")
        extra=read_csv(path,fields)
        if len(extra)!=metadata["records"]:raise ValueError("추가 주의 자료 행 수 불일치")
        seen={normalize_key(r.name) for r in records}
        for row in extra:
            key=normalize_key(row["name"])
            if not key or key in seen or any(not value.strip() for value in row.values()):raise ValueError("추가 주의 자료의 빈 항목·중복 성분명")
            validate_evidence(row["source_url"],row["checked_on"]);seen.add(key);records.append(CautionRecord(**row))
    elif (root/"data/caution_additions_sources.json").exists():raise ValueError("추가 주의 CSV가 없습니다.")
    return records


def apply_detail_taxonomy(root, records):
    """현재 명칭→검증한 선택적 7분류→같은 레코드+추정 근거. 기존 4분류는 보존."""
    data=root/'data';path=data/'origin_taxonomy_sources.json'
    FILES = ("origin_additions.csv","origin_additions_sources.json", "origin_additions_round2.csv","origin_additions_round2_sources.json",
             "origin_additions_round3.csv","origin_additions_round3_sources.json", "origin_additions_round4.csv","origin_additions_round4_sources.json",
             "caution_additions.csv","caution_additions_sources.json","origin_detail_audit.csv")
    if not path.exists():
        if any((data/name).exists() for name in FILES if name.startswith('origin_')):
            raise ValueError('7분류 확장 자료의 출처 집계가 없습니다.')
        return records
    try:
        meta=json.loads(path.read_text(encoding='utf-8'))
        if meta['format_version']!=1 or meta['taxonomy_version']!=1:raise ValueError('지원하지 않는 7분류 자료 버전')
        date.fromisoformat(meta['imported_on'])
        for name,expected in meta['base_files'].items():
            if Path(name).name!=name or not (data/name).is_file() or hashlib.sha256((data/name).read_bytes()).hexdigest()!=expected:
                raise ValueError('7분류 기본 DB 체크섬 불일치: '+name)
        if set(meta['files'])!=set(FILES):raise ValueError('7분류 파일 집계를 확인해 주세요.')
        for name in FILES:
            if not (data/name).is_file() or hashlib.sha256((data/name).read_bytes()).hexdigest()!=meta['files'][name]:
                raise ValueError('7분류 자료 체크섬 불일치: '+name)
        canonical={normalize_key(r.name):r for r in records}
        inferred=set();individual=set()
        for name in FILES:
            if not name.startswith('origin_additions') or not name.endswith('.csv'):continue
            entries=read_csv(data/name,{'name','origin','reason','source_url','checked_on','evidence_level'})
            sidecar=json.loads((data/(Path(name).stem+'_sources.json')).read_text(encoding='utf-8'))
            if len(entries)!=sidecar['records'] or hashlib.sha256((data/name).read_bytes()).hexdigest()!=sidecar['sha256']:
                raise ValueError('추가 유래 행 수·체크섬 불일치: '+name)
            seen=set()
            for row in entries:
                key=normalize_key(row['name'])
                if key in seen or key not in canonical or row['origin'] not in ORIGINS or not row['reason'].strip():raise ValueError('추가 유래 이름·분류 오류: '+row['name'])
                if row['evidence_level'] not in {'individual_source','name_inference','name_identity','botanical_name_inference'}:raise ValueError('추가 유래 근거 수준 오류')
                validate_evidence(row['source_url'],row['checked_on']);seen.add(key)
                (individual if row['evidence_level']=='individual_source' else inferred).add(key)
        audit=read_csv(data/'origin_detail_audit.csv',{'name','legacy_origin','detail_category','confidence','reason','source_url'})
        from collections import Counter
        if len(audit)!=meta['records'] or len(audit)!=len(records) or dict(Counter(r['detail_category'] for r in audit))!=meta['category_counts'] or dict(Counter(r['confidence'] for r in audit))!=meta['confidence_counts']:
            raise ValueError('7분류 행 수·집계 불일치')
        mapped={}
        for row in audit:
            key=normalize_key(row['name'])
            if key in mapped or key not in canonical or row['detail_category'] not in DETAIL_ORIGINS or not row['confidence'].strip() or not row['reason'].strip():
                raise ValueError('7분류 이름·범주·근거 오류: '+row['name'])
            if row['legacy_origin'] not in ORIGINS:raise ValueError('7분류 이전 범주 오류')
            if not safe_source_url(row['source_url']):raise ValueError('7분류 출처 URL 오류')
            mapped[key]=row
        if set(mapped)!=set(canonical):raise ValueError('7분류 명칭 누락·불일치')
        updated=[]
        for rec in records:
            key=normalize_key(rec.name);row=mapped[key]
            estimate=(row['detail_category']!='확인 필요' and
                      (key in inferred or '추정' in row['confidence'] or '자동' in row['confidence'] or
                       (rec.origin=='확인 필요' and key not in individual)))
            updated.append(replace(rec,detail_origin=row['detail_category'],detail_confidence=row['confidence'],
                                   detail_reason=row['reason'],detail_source_url=row['source_url'],detail_is_estimate=estimate))
        return updated
    except (KeyError,TypeError,json.JSONDecodeError) as exc:
        raise ValueError('7분류 출처 집계의 형식을 확인해 주세요.') from exc
