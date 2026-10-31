"""터미널: python -m scripts.prepare_ocr. 설치 오류는 artifacts/ocr-setup.txt에도 저장."""
import importlib
import platform
import sys

from core.database import ROOT
from core.ocr import OCREngine
from scripts.ocr_downloads import guidance, prepare_all, safe_error


def prepare(emit):
    emit(f'Python {platform.python_version()} · {platform.system()} · {platform.machine()}')
    for name in ('torch','torchvision','easyocr','tesserocr','onnxruntime'):
        try:
            module=importlib.import_module(name)
            emit(f'{name}: 불러오기 성공 · {getattr(module,"__version__","설치됨")}')
        except Exception as exc:
            emit(f'{name}: {type(exc).__name__}: {safe_error(exc)}')
            emit('라이브러리 불러오기에 실패했습니다. 모델 다운로드 실패와 구분해 위 오류를 확인해 주세요.')
            return 1
    try:
        prepare_all(ROOT/'.cache',emit)
    except Exception as exc:
        emit(f'모델 준비 실패: {type(exc).__name__}: {safe_error(exc)}')
        emit(guidance(exc))
        return 1
    engine=OCREngine()
    for label,action in [('새 한국어 줄 인식 엔진',engine.prepare_neural),('글자 영역 엔진',engine.prepare),('인쇄 글자 엔진',engine.prepare_accurate)]:
        emit(label+'을 확인하고 있습니다.')
        result=action()
        if result.status!='ready':
            emit(f'{result.status}: {result.message}')
            return 1
    emit('한국어·영어 CPU OCR 준비 완료. 모델 SHA-256 검증과 실제 엔진 초기화를 통과했습니다.')
    return 0


def main():
    path=ROOT/'artifacts/ocr-setup.txt'
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',encoding='utf-8') as log:
            def emit(message):
                print(message,flush=True);log.write(message+'\n');log.flush()
            status=prepare(emit)
            emit('설치 진단 파일: artifacts/ocr-setup.txt · 사진/프록시 환경 변수는 기록하지 않습니다.')
            return status
    except OSError as exc:
        print(f'설치 진단 파일 저장 실패: {type(exc).__name__}: {safe_error(exc)}',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
