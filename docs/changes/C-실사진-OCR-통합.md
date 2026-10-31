# C: 실제 사진 OCR 공통 연결 반영

A의 `A-실사진-한국어모델.md` 요청을 반영했다. recognize_photo/prepare_review,
AnalysisRequest/AnalysisResult, ScanOutput와 v1 상태/필드는 유지하여 별도의 자료형 어댑터는 필요 없다.
UI 모델/사진 처리 캐시는 PIPELINE_VERSION=ppocr-v5-korean-1로 갱신한다.

공식 PP-OCRv5 검출·한국어 ONNX/문자사전을 배포 커밋과 SHA-256으로 고정했다.
Python3.14 Windows/Linux용 onnxruntime CPU와 PyYAML을 명시하고 setup/재시도에서 초기화를 검사한다.
사진은 외부 AI로 보내지 않는다. 함량 주석은 이름 대조에서만 분리하며 B의 amount를 확정하지 않는다.

기존 B 분석을 포함한 pytest92개, 서버, 실제 CPU 모델 인공 라벨·회전/곡면 5종을 통과했다.
Windows x64 Python3.14.9에서도 설치·기존 환경 보존·모델 재사용/재시도·동일 기능 검사 및 실제 대표6장 검사를 통과했다.
실제42장 검사와 목표 미달/영역 미탐지는 docs/a/real-photo-ocr.md에서 OS별로 따로 보고한다.
