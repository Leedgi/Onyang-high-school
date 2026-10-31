# 학생들이 새롭게 만드는 화장품 성분 분석 사이트

기존 구현에서 OCR·후처리·분석 엔진과 실자료만 가져오고, 화면·서비스 연결은 작은 기본 틀로 새로 만들었다.
서비스 이름·디자인·정보 배치·학생별 추가 기능은 직접 정한다. 가상 예제 메뉴는 없다.

**사용 흐름:** 사진 업로드 → 자동 영역·전처리·OCR·이름 대조 → 목록 확인 한 번 → 분석·표·그래프.
불확실한 이름만 바로 후보를 선택할 수 있다. 후보 적용·별도 OCR 시작·별도 계산 버튼을 연속해서 누를 필요가 없다.
사진 없이 이름을 입력해도 같은 DB로 분석한다.

## 처음 실행: Windows

1. 이 폴더를 새 프로젝트의 최상위로 사용한다. 기존 프로젝트의 app.py·ui를 위에 덮어쓰지 않는다.
2. [Python 3.14 x64 설치 파일](https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe)을 설치한 컴퓨터에서 `setup_windows.bat`을 한 번 실행한다. 최초 모델 다운로드에는 인터넷이 필요하다.
3. `run_windows.bat`을 실행하면 브라우저가 열린다. 성분표 사진을 올리면 자동으로 읽기 시작한다.
4. 인식한 목록을 원본과 비교하고 필요한 이름만 수정한 뒤 `목록 확인 완료 · 분석 보기`를 누른다.

이번 Python 3.12 → 3.14 전환 때는 실행 중인 앱을 종료하고 Python 3.14 설치 후 setup을 한 번 실행한다. 기존 `.venv`는 `.venv-backups/`에 보존하고 새 3.14 환경을 만든다. OCR 모델 `.cache`는 유지한다. 이후 코드만 업데이트했다면 앱 재시작으로 충분하다. requirements나 모델 구성이 바뀌었을 때 setup을 다시 실행한다.
개발 PC의 localhost 실행과 인터넷 공개 배포는 다르다. 현재 공개 주소·도메인·운영 서버는 만들지 않았다.
공개 배포는 C가 대상 호스팅의 메모리·CPU OCR 시간·HTTPS·사진 처리 방침·모델 사전 준비를 확인해 진행한다.

Linux/Codex 검증 환경: `python -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`,
`.venv/bin/python -m scripts.prepare_ocr`, `.venv/bin/python -m streamlit run app.py`.
실제 Windows 호스트 검증은 GitHub Actions의 Windows 작업과 구분한다.

## 새 GitHub 저장소와 3개 브랜치

GitHub에서 새 **빈 저장소**를 만든다(README·라이선스·gitignore 자동 생성은 선택하지 않는다).
새 저장소를 사용할 계정은 Git 설치와 GitHub 로그인이 되어 있어야 한다. 토큰·비밀번호를 코드나 채팅에 넣지 않는다.
이 폴더에서 터미널/PowerShell을 열고 다음을 실행한다. URL은 실제 새 저장소 주소로 바꾼다.

```powershell
py -3.14 scripts/bootstrap_branches.py --remote https://github.com/계정/새저장소.git --publish
```

Git 작성자 정보가 없다는 오류가 나면 자신의 이름·메일을 Git에 설정한 뒤 같은 명령을 다시 실행한다.
명령은 main 최초 커밋과 세 브랜치를 준비해 새 origin에 올린다. 이미 다른 원격이 연결돼 있으면 바꾸거나 덮어쓰지 않고 멈춘다.
GitHub의 기본 브랜치가 main인지 확인한다. 각 학생은 새 저장소의 **서로 다른 체크아웃**에서 자기 브랜치를 사용한다.
이미 clone한 저장소에 이 파일을 복사했다면 변경을 커밋한 뒤 main에서 명령을 실행한다.
원격 연결 없이 로컬 브랜치만 만들려면 `py -3.14 scripts/bootstrap_branches.py`를 실행한다.

| 학생 | 브랜치 | Codex에 넣을 문서 |
| --- | --- | --- |
| A | feature/a-recognition | prompts/00_COMMON.md + prompts/A.md |
| B | feature/b-analysis | prompts/00_COMMON.md + prompts/B.md |
| C | feature/c-web | prompts/00_COMMON.md + prompts/C.md |

처음 프로젝트를 준비할 Codex에는 `prompts/START_HERE.md`를 준다.
규격과 역할별 지시까지 한 문서로 전달하려면 `prompts/MASTER_PROMPT.md`를 사용한다.
원래 예시 코드 전체만 받았더라도 이 문서가 `student-starter/`를 독립 프로젝트로 꺼내는 방법을 안내한다.
공통 변수·자료형·함수는 [CONTRACTS](docs/CONTRACTS.md), 담당 경로와 변경 절차는 [OWNERSHIP](docs/OWNERSHIP.md)에서 확인한다.
통합 담당 C가 PR을 합칠 때는 `prompts/INTEGRATE.md`를 사용한다.

## 자료와 구현 범위

- 통합 DB 32,797개 성분(개별 검토·정의 규칙 대조 6,143개 / 이름 전용 26,654개), 정확 이름·별칭 검색 키 57,706개. KCIA 공개 표준화 명칭 22,021행과 공개 정의 144개 검토를 추가했다. 회원사 전용 유래 항목은 열람하지 않았으며 원료 공급원이 불명확한 화학명은 확인 필요다. 기존 270개/28,077개 자료는 고정 원본 구성으로 보존한다. 출처·확인일·범위는 data/README.md와 kcia_sources.json을 따른다.
- 이름 전용 항목의 유래는 전부 확인 필요다. 일부 정의는 2019 공개 스냅샷이며 최신 규제·안전성 자료가 아니다.
- 주의 DB에는 FDA 인체 주의 27개 물질과 PubChem/HSDB 환경 시험 3개 물질(한글·INCI·구명칭 63행)이 들어 있다. 국가·농도·사용 조건과 자료 시점을 구분해 표시한다. 대체 성분·제품 CSV는 현재 헤더만 있다. 추천·제품 비교는 아직 구현되지 않았다.
- EasyOCR/CRAFT 영역 탐색 + Tesseract LSTM 재인식 + 정규화/RapidFuzz 후보. 외부 LLM 키는 필요 없다.
- 원문·교정 기록·불확실한 후보를 보존한다. 반사·곡면·흐림 등으로 틀릴 수 있어 완벽한 OCR이라고 주장하지 않는다.
- 참조 엔진의 출발점은 기존 저장소 커밋 b6b618c다. 원래 화면·가상 DB·사용자 사진·모델 가중치·비밀값·기존 Git 이력은 포함하지 않았다.
- 최소 화면은 사용 가능하지만 완성된 브랜드 사이트가 아니다. 학생들이 사용성·정보 구조·실제 사진 평가·추천 자료를 발전시킨다.

## 검사

Windows: `check_windows.bat`. 개발 터미널: `python -m pytest -q`, `python -m scripts.check_server`.
실제 모델/자동 영역 인식: `python -m scripts.check_auto_ocr`(모델 준비 후 실행).
tests의 인공 라벨·오류 주입 텍스트는 회귀 검사용이며 사용자 메뉴나 실제 제품 정확도 증거가 아니다.
검증한 내용은 docs/VALIDATION.md에 기록한다.


### 곡면·거꾸로 된 성분표와 KCIA 확장

사진 입력 → 0/180/90/270도 비교 → 기존 보정과 조건부 곡면 대안 비교 → 미확정 이름 목록을 표시한다. 한 방향의 실행 오류가 나머지 방향 탐색을 막지 않는다. 흐림·반사광으로 지워진 글자를 보장해서 복원하지 않는다. 네 방향을 검사하므로 CPU 처리 시간이 늘 수 있다. 실제 모델의 인공 라벨 검사와 촬영 사진 성능은 구분한다(`docs/a/orientation-curvature.md`).

DB 입력 → 체크섬·정확 명칭·충돌 검사 → 같은 AnalysisResult와 그래프/PDF를 생성한다. 자료가 바뀌거나 검증에 실패하면 이전 결과를 지우고 재확인을 요구한다. 명칭만 등재된 항목과 제조 공급원이 불명확한 항목은 확인 필요다. 유래는 제품의 안전·친환경성 등급이 아니다.

2026-10-30 데이터·OCR 변경 당시에는 실행 의존성 추가가 없어 파일 갱신과 앱 재시작으로 충분했다. 2026-10-31 Python 3.14 전환은 위 안내대로 setup을 한 번 실행한다. 최초 설치나 기존 의존성이 없는 환경에서만 `setup_windows.bat`이 필요하다. 이번 검증은 Linux Python 3.12 CPU에서 수행했으며 Windows 실기 실행과 구분한다.

### Windows 검사와 추가 유래 근거 (2026-10-30)

실제 GitHub Windows x64/Python 3.12 러너에서 setup_windows.bat, 전체60개 검사, 실제 CPU OCR, 서버 검사를 통과했다([실행41070170583](https://github.com/Leedgi/Onyang-high-school/actions/runs/41070170583)). 사용자 개인 PC를 원격으로 검사한 것은 아니다. Git의 CSV/JSON 줄바꿈 변환 때문에 생기던 체크섬 실패를 .gitattributes의 LF 고정으로 수정했다.

추가5,749개 유래는 고정2019 정의의 명시적 근거를 규칙으로 대조한 결과이며 모두 최신 개별 수동 검토라고 표현하지 않는다. 식물성5,504/석유계11/기타234개를 보완해 통합 유래는 식물성5,679/석유계17/기타278/확인필요26,823개다. 자세한 범위는 data/origin_sources.json과 data/README.md를 따른다. 제조 경로가 여러 개인 주요5개 성분은 원문과 경로 설명을 표시하며 origin_uncertain을 유지한다. 새 의존성은 없다.


### OCR 모델 준비 중 URLError가 나올 때

URLError는 모델을 받는 네트워크 단계의 오류다. 예전 공통 문구에 있던 저장 공간·권한 문제가 확정된 것은 아니다. 최신 설치 스크립트는 주소 조회/DNS, 인증서, 연결 시간 초과 등 실제 원인을 `artifacts/ocr-setup.txt`에 UTF-8로 남긴다. 사진이나 프록시 환경 변수는 기록하지 않는다.

의존성 설치를 이미 마쳤다면 **retry_ocr_windows.bat**을 실행해 모델만 다시 준비한다. 명령으로 실행하려면 저장소 폴더의 PowerShell에서 `.\.venv\Scripts\python.exe -m scripts.prepare_ocr`만 실행해 모델 준비를 재시도한다. 검증된 모델은 재사용한다. Python 다운로드가 두 번 실패하면 Windows 기본 curl로 공식 HTTPS 주소를 재시도하며 인증서 검증과 고정 SHA-256 검증을 유지한다. 검증되지 않은 파일은 사용하지 않는다.

계속 연결에 실패하면 휴대폰 핫스팟 같은 다른 네트워크에서 같은 명령을 실행해 학교·회사망 제한인지 구분할 수 있다. 인증서 오류일 때는 PC 날짜·시간과 네트워크 인증서 설정을 확인한다. SSL 검증이나 보안 프로그램을 끄는 방식은 사용하지 않는다. 새 진단 TXT에서 실제 오류를 확인해 문의한다.
