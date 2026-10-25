"""실제 CPU 모델로 인공 전체 라벨의 이전 방식과 자동 영역·분리 방식을 비교한다."""
from dataclasses import asdict
import json
from pathlib import Path
import time

from PIL import Image

from core.database import ROOT, load_ingredients
from core.normalize import normalize_key, normalize_text
from core.ocr import OCREngine
from core.scan import scan_ingredients


def evaluate(names: list[str], expected: list[str], database) -> dict:
    def key(name):
        record = database.find(name)
        return normalize_key(record.name if record else name)
    predicted = {key(name) for name in names}
    target = {key(name) for name in expected}
    true = len(predicted & target)
    return {"matched": true, "expected": len(target), "predicted_unique": len(predicted),
            "name_recall": true / len(target), "name_precision": true / max(1, len(predicted)),
            "missing": [name for name in expected if key(name) not in predicted]}


def main() -> int:
    fixture = ROOT / "tests/fixtures/dense_label.png"
    target = json.loads((ROOT / "tests/fixtures/dense_label.expected.json").read_text(encoding="utf-8"))
    database = load_ingredients()
    engine = OCREngine()
    started = time.monotonic()
    with Image.open(fixture) as image:
        # 이전 앱과 같은 전체 사진 1회 greedy 인식 + 물리적 줄/쉼표 분리.
        baseline = engine.recognize(image)
        output = scan_ingredients(image, engine, database, progress=lambda text: print(text, flush=True))
    if baseline.status != "ok" or output.result.status != "ok":
        print("Actual OCR failed:", baseline.status, output.result.status, output.result.message)
        return 1
    before = evaluate([token.name for token in normalize_text(baseline.raw_text)], target["names"], database)
    raw = evaluate([draft.raw_text for draft in output.result.ingredients], target["names"], database)
    proposed = evaluate([draft.name for draft in output.result.ingredients], target["names"], database)
    artifact = ROOT / "artifacts/auto-ocr-comparison.json"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(json.dumps({
        "fixture": target["description"], "expected_names": target["names"],
        "baseline": {"ocr": asdict(baseline), "metrics": before},
        "automatic": {"scan": asdict(output.result), "raw_name_metrics": raw, "unconfirmed_proposal_metrics": proposed},
        "seconds": time.monotonic() - started,
        "limits": "인공 라벨 한 장의 이름 단위 비교. 사용자 원본 사진이나 일반적인 정확도 수치가 아니며 교정 제안은 미확정이다.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    output.image.save(ROOT / "artifacts/auto-ocr-selected-region.png")
    print("Baseline:", before, flush=True)
    print("Automatic OCR names:", raw, flush=True)
    print("Unconfirmed proposals:", proposed, flush=True)
    print("Report:", artifact, flush=True)
    if (output.result.processing.get("region_method") == "not_found"
            or proposed["matched"] < max(4, before["matched"])):
        print("자동 영역·분리 방식의 시험 라벨 동작 확인에 실패했습니다.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
