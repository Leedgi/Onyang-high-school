# URLError 다운로드 복구와 설치 진단

2026-10-31 한국 시간. 사용자에게 표시된 URLError는 네트워크 실패를 가리키지만 기존 메시지는 내부 reason을 버리고 저장 공간·권한·연결의 공통 안내만 표시했다. 인증서/DNS/시간 초과 등 세부 원인은 아직 사용자 PC에서 관찰하지 못했으므로 확정하지 않는다.

입력: 기존 고정 공식 모델 URL과 캐시. 처리: 먼저 SHA-256을 검증해 맞는 모델은 재사용한다. 필요한 파일만 Python HTTPS로 최대2회 시도하고, Windows에서는 실패 시 기본 System32/curl.exe로 같은 공식 HTTPS URL을 재시도한다. 인증서 확인과 HTTPS 리디렉션 제한을 유지하며 임시 파일의 고정 SHA-256이 맞을 때만 원자적으로 반영한다. ZIP은 지정된 모델 멤버만 읽는다. SHA는 기존 공식 EasyOCR1.7.2 모델(CRAFT, korean_g2)의 MD5 검증 및 엔진 로딩을 통과한 파일과 기존 고정 Tesseract revision의 파일을 기준으로 고정했다. 임의 미러·SSL 우회는 추가하지 않는다.

출력: 이전과 같은 OCREngine 준비 결과와 artifacts/ocr-setup.txt(UTF-8). 실제 오류 종류/reason과 단계별 성공을 기록한다. URL의 인증정보/쿼리는 지우고 사진/프록시 환경 변수는 기록하지 않는다. 실패: 유효하지 않은 다운로드로 기존 파일을 덮지 않고 임시 파일을 정리한다. 계속 막히면 다른 네트워크에서 접근 제한을 구분하고 새 TXT의 실제 원인을 확인한다.

재시도는 retry_ocr_windows.bat으로 모델만 실행한다. 전체 pip 설치나 Python 재설치는 하지 않는다. 같은 동작은 .venv\\Scripts\\python.exe -m scripts.prepare_ocr다. 공개 함수/모델/enum/CSV/의존성 버전은 유지하며 A 인식 로직은 수정하지 않는다. 기존 유효 모델은 추가 다운로드 없이 재사용한다.

검증: Linux Python3.14에서 전체75개 검사와 서버 검사를 통과했다. 다운로드 실패/재시도, 인증서 오류 주입 후 native curl 호출과 TLS 옵션 유지, 잘못된 해시일 때 기존 파일 보존, ZIP 경로, 기존 캐시의 네트워크 미사용, 세부 오류 TXT/URL 자격정보 제거를 검사한다. 기존 OCR 엔진 초기화도 통과했다. Windows workflow는 빈 캐시에 실제 공식 모델을 받고, Python TLS 실패를 주입한 별도 검사에서 실제 Windows curl HTTPS로 고정 영어 모델을 받은 뒤 SHA를 확인한다. 이 주입 시험은 사용자 PC에서 실패를 직접 재현했다는 뜻이 아니다. 재시도 배치와 전체 pytest/실제 CPU OCR/서버도 검사한다.
