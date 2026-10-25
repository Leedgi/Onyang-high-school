"""고정된 공개 자료를 체크섬 검증해 교육용 성분 DB를 재생성한다. 앱 실행 때는 다운로드하지 않는다."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

from core.database import ROOT
from core.normalize import normalize_key

CHECKED_ON = "2026-10-24"  # 이 고정 자료의 검토일. 재실행일을 검토일로 위장하지 않는다.
SOURCES = {
    "identifiers": {
        "url": "https://raw.githubusercontent.com/beauteeru/cosmetic-ingredients-dataset/ad1d9afad3f1a721873878b83fbd9f674d628c9e/ingredients.csv",
        "source_url": "https://github.com/beauteeru/cosmetic-ingredients-dataset/blob/ad1d9afad3f1a721873878b83fbd9f674d628c9e/ingredients.csv",
        "sha256": "d7dab26eca24ac3b6235291ff2d1021e078be4382bbca772a1178f7e3e516625",
        "filename": "identifiers.csv",
        "scope": "INCI 이름·식별자만 제공. 유래·안전성·사용 허용의 근거가 아님. MIT License.",
    },
    "cosing": {
        "url": "https://raw.githubusercontent.com/walkowskis/CosIng_database_finder/d3dbd5644813ef6c1bff59b6b075fec54a1eaaff/testowa.db",
        "source_url": "https://github.com/walkowskis/CosIng_database_finder/blob/d3dbd5644813ef6c1bff59b6b075fec54a1eaaff/testowa.db",
        "sha256": "6d93d0f4d7d7251d139ee149c6a15705a18fc3c453ffc61bf23e63cd2ffedcbb",
        "filename": "cosing-2019.db",
        "scope": "2019-03-16 공개 스냅샷의 정의·기능을 조회한 비공식 미러. 최신 규제·안전성 판단에 사용하지 않음.",
    },
}
FUNCTIONS = {
    "EMOLLIENT": "유연", "HUMECTANT": "보습", "MOISTURISING": "보습",
    "SKIN CONDITIONING": "피부컨디셔닝", "SKIN PROTECTING": "피부보호",
    "VISCOSITY CONTROLLING": "점도조절", "EMULSIFYING": "유화", "SURFACTANT": "계면활성",
    "EMULSION STABILISING": "유화안정화", "SOLVENT": "용제", "BINDING": "결합",
    "OPACIFYING": "불투명화", "FILM FORMING": "피막형성", "ANTIOXIDANT": "산화방지",
    "CHELATING": "금속이온봉쇄", "PRESERVATIVE": "보존", "PERFUMING": "향료",
    "MASKING": "냄새완화", "SOOTHING": "진정", "ANTIFOAMING": "기포방지",
    "ANTISTATIC": "정전기방지", "HAIR CONDITIONING": "모발컨디셔닝",
}


def get_source(cache: Path, source: dict) -> Path:
    path = cache / source["filename"]
    if not path.exists():
        with urllib.request.urlopen(source["url"], timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError("다운로드 원본의 SHA-256이 일치하지 않습니다. 사용하지 않습니다.")
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError(f"{path.name}: 저장된 원본 체크섬이 일치하지 않습니다.")
    return path


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(cache: Path, target: Path = ROOT / "data") -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    original = {key: get_source(cache, source) for key, source in SOURCES.items()}
    curated = []
    evidence = []
    keys = set()
    with sqlite3.connect(original["cosing"].as_uri() + "?mode=ro", uri=True) as connection:
        for spec in csv.DictReader((target / "curation.csv").open(encoding="utf-8", newline="")):
            found = connection.execute(
                "SELECT Ref_No, INCI_name, Chem_Name, Function FROM cosing WHERE trim(INCI_name)=? COLLATE NOCASE",
                (spec["inci"],),
            ).fetchone()
            if found is None:
                raise ValueError(f"정의 원문에 없는 성분: {spec['inci']}")
            ref, inci, definition, functions = found
            definition = "\n".join(line.rstrip() for line in definition.splitlines()).strip()
            functions = functions.strip()
            kind = spec["kind"]
            prefix = f"2019 CosIng 공개 스냅샷(비공식 미러), Ref {ref}: "
            origin, uncertainty = "확인 필요", "origin_uncertain"
            if kind == "plant":
                origin, uncertainty = "식물성", ""
                reason = "정의상 식물에서 얻는 오일·버터·왁스·추출물·증류물입니다. 추출 용매·부원료·실제품 전체의 유래를 보증하지 않습니다."
            elif kind == "petroleum":
                origin, uncertainty = "석유계", ""
                reason = "정의상 석유 탄화수소 또는 그 정제·탈랍으로 얻는 원료입니다. 석유계라는 분류가 위해성 판정은 아닙니다."
            elif kind == "silicone":
                origin, uncertainty = "기타", ""
                reason = "실리콘·실록세인계 성분으로 기타에 분류합니다. 전구체의 공급 원료까지 석유계·식물성으로 단정하지 않습니다."
            elif kind == "animal":
                origin, uncertainty = "기타", ""
                reason = "정의상 벌집 왁스 또는 양의 분비물 유래 원료입니다. 동물 유래는 기타에 분류합니다."
            elif kind == "other":
                origin, uncertainty = "기타", ""
                reason = "물·무기염·산화물·광물계 성분으로 기타에 분류합니다. 천연 채굴인지 합성 제조인지는 별도 확인 대상입니다."
            elif kind == "uncertain":
                reason = "성분의 정의·기능은 조회했지만 실제 제조사의 원료 공급원과 제조 경로는 확인되지 않았습니다. 이름이나 합성 여부만으로 석유계·식물성을 단정하지 않습니다."
            else:
                raise ValueError(f"알 수 없는 검토 종류: {kind}")
            if not definition.strip():
                if kind != "uncertain":
                    raise ValueError(f"정의가 비어 있는 성분의 유래를 확정할 수 없습니다: {inci}")
                uncertainty = "evidence_insufficient"
                reason = "자료에 이름·기능은 있지만 화학적 정의가 비어 있으며 실제 제조 원료도 확인되지 않았습니다. 유래 근거 부족으로 확인 필요에 둡니다."
            aliases = [spec["inci"], *filter(None, spec["aliases"].split(";"))]
            for name in [spec["name"], *aliases]:
                key = normalize_key(name)
                # 같은 성분 내 표기 중복은 허용하되 서로 다른 성분의 별칭 충돌은 금지한다.
                if key in keys:
                    raise ValueError(f"서로 다른 성분 사이에 중복된 이름: {name}")
            keys.update(normalize_key(n) for n in [spec["name"], *aliases])
            tags = list(dict.fromkeys(FUNCTIONS.get(f.strip(), f.strip()) for f in functions.split(",") if f.strip()))
            curated.append({
                "name": spec["name"], "aliases": "|".join(aliases), "origin": origin,
                "reason": prefix + reason, "functions": "|".join(tags),
                "source_url": SOURCES["cosing"]["source_url"], "checked_on": CHECKED_ON,
                "uncertainty_reason": uncertainty,
            })
            evidence.append({"name": spec["name"], "inci": spec["inci"], "ref": ref,
                             "definition": definition, "functions": functions, "review_kind": kind})
    registry = []
    for row in csv.DictReader(original["identifiers"].open(encoding="utf-8-sig", newline="")):
        name = row["name"].strip().upper()
        key = normalize_key(name)
        if not key or key in keys:
            continue
        keys.add(key)
        registry.append({"name": name, "cosing_id": row["substanceId"], "cas_no": row["casNo"],
                         "ec_no": row["ecNo"], "pubchem_id": row["pubchem_cid"]})
    write_csv(target / "ingredients.csv", list(curated[0]), curated)
    write_csv(target / "ingredient_names.csv", ["name", "cosing_id", "cas_no", "ec_no", "pubchem_id"], registry)
    write_csv(target / "source_evidence.csv", list(evidence[0]), evidence)
    manifest = {"checked_on": CHECKED_ON, "sources": SOURCES, "curated_records": len(curated),
                "registry_records": len(registry), "origin_counts": {origin: sum(r["origin"] == origin for r in curated)
                for origin in ["석유계", "식물성", "기타", "확인 필요"]}}
    (target / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/ingredient-sources")
    args = parser.parse_args()
    print(json.dumps(build(args.cache.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
