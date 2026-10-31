# Python 3.14로 실행 환경 전환

2026-10-31 한국 시간. 기본 환경을 표준 CPython3.14 x64 CPU로 바꾼다. Python3.15는 현재 고정한 PyTorch2.10.0+cpu/TorchVision0.25.0+cpu 및 scikit-image0.26.0 조합의 Windows 배포 파일이 준비되지 않아 선택하지 않았다. PyPI 메타데이터와 PyTorch CPU 인덱스에서3.14 Windows 파일을 확인했다. 공식3.14.10 x64 설치 파일 URL도 HTTP200으로 확인했고 README와 설치 오류 안내에 연결했다.

입력: 설치된 표준3.14 Python과 기존 .venv. 처리: 버전·64비트·가상환경·GIL 빌드를 확인하고 맞으면 재사용한다. 다른 버전/손상 환경은 .venv-backups/에 보존한 뒤 새로 만든다. 출력: 기존 setup_windows.bat → run_windows.bat 흐름 그대로. 실패: 앱/터미널을 닫고 재시도하도록 안내하며 이전 환경을 백업에 보존한다. 모델 .cache와 사용자 데이터는 이동하지 않는다. 최초 버전 전환 때만 setup을 실행하고 실행 배치에서는 설치를 반복하지 않는다.

공개 함수·모델·DB/CSV·CONTRACT_VERSION=1과 의존성 고정 버전은 유지한다. Python 실행 환경만 바뀌며 A/B 내부 로직은 수정하지 않는다. 기존3.12 환경은 개인 PC에 설치된 Python과 별개로 백업되고 새3.14 가상환경을 만든다.

검증: 별도의 Linux Python3.14.8 환경에 전체 의존성을 설치했고 pip check, 전체68개 pytest, 서버 health/page 검사를 통과했다. 새 검사는 공백 경로, 실제 가상환경 생성/재사용, 기존 폴더/모델 보존, 재실행 시 중복 백업 방지를 확인한다. 실제 CPU 인공 라벨 검사도 별도 실행한다. Windows workflow는 실제3.12 가상환경과 보존 표식을 먼저 만들고3.14로 전환한 뒤, 이전3.12 인터프리터/표식 보존과 재시도 재사용, 전체 pytest·CPU OCR·서버를 검사한다. 최종 Windows 실행 결과는 PR workflow 링크로 구분해 보고한다. 사용자 개인 PC를 원격으로 검사한 것은 아니다.

근거: https://www.python.org/downloads/release/python-31410/ , https://download.pytorch.org/whl/cpu/torch/ , https://pypi.org/project/scikit-image/0.26.0/#files . 인공 라벨의 실행 확인은 실제 촬영 사진의 일반 인식 정확도를 입증하지 않는다.
