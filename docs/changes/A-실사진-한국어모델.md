# C에게: 실제 사진용 한국어 PP-OCRv5 연결

42장 사용자 시험 사진에서 기존 CRAFT/Tesseract가 영역 미탐지·작은 한글 혼합을 보였다.
공개 recognize_photo/prepare_review와 v1 자료형은 유지한다. 새 엔진은 로컬 ONNX CPU이며 사진을 외부로 보내지 않는다.

C 반영 요청: onnxruntime CPU(3.14 Windows/Linux 휠), 공식 PaddlePaddle PP-OCRv5 검출·한국어 ONNX/문자사전의 고정 커밋·SHA 다운로드,
prepare_ocr와 Windows 검사, UI 모델 캐시 버전 갱신, 실제 사진별 평가 스크립트.
설치 실패는 기존 공통 오류 상태로 전달한다. 정답 목록은 samples/ocr 평가에서만 읽고 core에서는 참조하지 않는다.
