"""터미널: 저장소 폴더에서 python -m scripts.prepare_ocr"""
from core.ocr import OCREngine


def main() -> int:
    engine = OCREngine()
    print("AI 글자 영역 검출 모델을 준비하고 있습니다.", flush=True)
    result = engine.prepare()
    if result.status != "ready":
        print(f"{result.status}: {result.message}")
        return 1
    print("인쇄 글자 LSTM 모델을 준비하고 있습니다. 최초 추가 다운로드는 약 28MB이며, 기존 파일은 검증 후 재사용합니다.", flush=True)
    result = engine.prepare_accurate()
    if result.status != "ready":
        print(f"{result.status}: {result.message}")
        return 1
    print("한국어·영어 CPU OCR 모델 준비 완료. EasyOCR 검출 모델과 인쇄 글자 LSTM 모델의 체크섬 검증을 사용했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
