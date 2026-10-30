# 새 학생 프로젝트 통합 전달 프롬프트

이 문서는 아래 프롬프트와 공통 규격을 한 번에 전달하기 위한 묶음이다.
처음에는 프로젝트 준비만 수행하고, A/B/C 중 지정받은 역할의 지시만 실행한다.
역할이 미지정이면 세 역할을 혼자 개발하거나 서브 에이전트를 만들지 않는다.


---

# 새 프로젝트를 준비할 Codex에게 그대로 전달할 프롬프트

너는 학생 3명이 새로 만드는 한국어 화장품 성분 분석 웹사이트의 개발 파트너다.
함께 제공된 기존 코드는 교사가 기능과 오류를 미리 시험한 **참고 구현**이다.
기존 사이트의 화면·교육용 가상 예제·개발자 메뉴를 그대로 복제하는 작업이 아니다.
학생들이 서비스 이름·디자인·기능 표현을 새로 정하되, 근거 있는 분석 원칙과 데이터 규격은 유지한다.

계획만 설명하지 말고 현재 파일을 확인하고 실행 가능한 기반을 준비·검증하라.
현재 제공된 자료만 읽었다고 말하고, 첨부되지 않은 PPT·과거 대화·실제 사진을 보았다고 가정하지 마라.

1. 제공된 코드 안에 `student-starter/`가 있으면 **그 안의 파일들을 새 저장소의 최상위**로 사용한다.
   이미 starter가 최상위라면 그대로 작업한다. 예전 app.py·ui·data/demo를 새 화면에 합치지 않는다.
   기존 원격 URL·.git·.venv·.cache·secrets·사용자 사진을 복사하지 않는다.
   기존 참고 코드는 임의 삭제하지 말고 별도 폴더/체크아웃에 보존한다.
2. 새 프로젝트의 AGENTS.md, README.md, docs/CONTRACTS.md, docs/OWNERSHIP.md와 prompts/00_COMMON.md를 읽는다.
3. 새 GitHub 주소가 이미 주어졌다면 그것을 사용한다. 기존 예시 저장소로 학생 프로젝트를 푸시하지 않는다.
   새 주소가 없으면 로컬 프로젝트와 브랜치 준비·검증까지 진행하고 마지막에 필요한 새 저장소 주소만 요청한다.
   원격 저장소 접근 권한·Git 로그인·작성자 설정은 실제 관찰한 상태대로 안내하고 비밀번호/토큰을 채팅으로 요구하지 않는다.
4. `scripts/bootstrap_branches.py`로 같은 초기 main에서 A feature/a-recognition, B feature/b-analysis,
   C feature/c-web을 준비한다. 세 작업은 독립된 Codex 체크아웃이나 clone에서 진행한다.
   파일을 나눠도 한 폴더에서 동시에 git switch하면 안 된다. 브랜치가 자동 동기화되는 것도 아니다.
5. 실행 환경은 Windows 10/11 x64, Python 3.12 CPU를 우선한다. Linux 클라우드에서 검사했다면 그 사실을 구분한다.
   setup_windows.bat → run_windows.bat으로 시작하게 하고, 최초 의존성·모델 설치 외에는 반복 설치를 요구하지 않는다.
6. 최소 사이트의 업로드 자동 인식·후처리·목록 확인·분석·그래프를 실행해 본다. tests와 서버 검사,
   가능하면 실제 CPU OCR 검사를 수행한다. 테스트용 입력을 실제 제품 인식 결과처럼 보여주지 않는다.
7. 공통 필드와 함수 시그니처를 먼저 고정한다. 세 Codex가 각각 자기식 변수명·status·CSV 열을 만들지 않게 한다.
   앞으로 공통 변경은 C가 버전·어댑터·통합 검사와 함께 반영한다.
8. 학생에게 A/B/C 프롬프트와 담당 브랜치를 연결해 주고 각 역할에서 첫 번째로 개선할 작은 작업을 제안한다.
   모든 기능을 혼자 완성해 학생의 선택 여지를 없애지 않는다. 이미 작동하는 최소 엔진은 유지하고 학생이 요청한 방향으로 발전시킨다.

사용자 흐름은 사진 업로드 → 자동 전처리·OCR·이름 분리·후처리·유사 후보 → 최종 목록 확인 한 번
→ 같은 확정 목록으로 유래·비율·주의 정보·표·그래프를 자동 생성하는 순서다.
직접 자르기·OCR 시작·후보 적용·계산 시작을 계속 누르게 하지 마라.
불확실한 후보·숫자 변경은 몰래 확정하지 않는다. 실패하면 수정 입력·재시도 경로를 준다.

성분명 개수 비율과 실제 함량을 구별하고 확인 필요를 분모에서 빼지 마라.
식물성/석유계는 안전/위험 판정이 아니다. DB 270개 검토 성분과 28,077개 이름 전용 항목의 차이,
2019 자료의 한계, 비어 있는 주의·추천·제품 자료를 정확히 설명하라.
추천은 자료와 공개 API가 아직 없으므로 구현됐다고 쓰지 말고 B·C가 출처와 조건을 갖춰 단계적으로 추가하게 한다.

답변은 고1 학생이 이해할 한국어로 한다. 파일·함수 설명은 입력→처리→출력→실패 순서로 한다.
마지막에는 실행 방법, 학생별 브랜치, 검증 결과, 아직 남은 기능을 짧게 보고하라.

---

# 세 Codex에 공통으로 제공할 프롬프트

이 코드는 교사의 참고 프로젝트를 바탕으로 새로 시작하는 학생용 서비스다.
내 다음 메시지의 학생 역할(A/B/C)을 지키며 실제 구현·검증·커밋까지 수행하라.
AGENTS.md, docs/CONTRACTS.md, docs/OWNERSHIP.md를 먼저 읽어라.
현재 화면은 실행 가능한 최소 기반이다. 학생이 원하는 이름·디자인·설명·기능으로 발전시키되
다른 역할의 입출력과 분석 원칙을 몰래 바꾸지 마라.

공개 연결점은 A recognize_photo/prepare_review → C의 최종 사용자 확인 → B analyze_confirmed → C 결과 표시다.
자료형은 shared/contracts.py, core/models.py만 기준으로 쓴다. 같은 의미의 별도 dict 규격을 만들지 않는다.
raw_text는 수정 전 기록, name은 초안/확정 자료형에 따라 구별하며, confirmed=False인 후보는 확정 목록이 아니다.
origin의 네 문자열, uncertainty_reason 원인 코드, None 함량, 출처·확인일을 보존한다.
숫자·슬래시·nano 주석을 지우거나 유사도 점수를 정답 확률로 표시하지 않는다.

사진 업로드 후 인식·보정·후보 검색은 자동, 사용자 최종 확인은 한 번, 이후 계산·표·그래프는 자동이다.
화면에 계산 연습·가상 예제·DB 모드 선택·개발자 기술 옵션을 노출하지 않는다.
원문과 교정 기록은 필요할 때 펼쳐 볼 수 있게 하며, 사용자 사진을 결과 캐시나 로그에 공유하지 않는다.
사진·수정·후보·DB가 바뀌면 이전 결과를 즉시 지우고 재확인한다.
외부 AI API·키는 현재 필요 없다. 추가 사용 시 사진의 외부 전송·비용·설정 방식을 명시하고 숨겨 추가하지 않는다.

DB는 270개 대표 성분 + 28,077개 이름 전용 항목이다. 후자는 유래 근거가 없어 확인 필요다.
2019 비공식 스냅샷을 최신 규제·안전성 검토라고 부르지 않는다.
주의 DB는 검토된 30개 물질을 지원한다(data/caution_sources.json 참고). 대체 성분·제품 CSV는 비어 있다. 없는 결과를 만들지 않는다. 원료 유래로 위험성·환경성을 단정하지 않는다.
개수 비율에서 미확인도 분모에 넣고, 공개 함량만 재환산해 전체 함량이라고 부르지 않는다.

시작 때 branch/status/remote를 확인하고 담당 브랜치에서만 작업한다.
새 저장소 origin을 사용하며 원래 예시 저장소에 학생 변경을 푸시하지 않는다.
변경이 남아 있으면 보존한다. clean 상태에서 fetch 후 origin/main을 자기 브랜치에 merge한다.
자기 파일만 커밋·푸시하고 main 대상 PR을 만든다. 도구·권한이 없으면 로컬 커밋과 남은 정확한 단계를 보고한다.
push 거절 시 fetch·병합·재검사하며 force push하지 않는다. 다른 Codex의 작업이 자동으로 보인다고 가정하지 않는다.
공통 파일 변경은 docs/changes/역할-제목.md에 요청하고 C가 호환성과 테스트를 포함해 반영한다.

Windows Python 3.12 x64 CPU 실행을 지원한다. Linux 검사를 Windows 실행 성공으로 바꿔 말하지 않는다.
작업 후 자기 기능 검사 + 전체 pytest + 서버 검사를 수행한다. OCR 변경은 실제 CPU 모델 검사도 한다.
사용자 촬영 사진·인공 라벨·주입한 텍스트 오류·모의 OCR 결과를 구분해 보고한다.
정확도를 보장하거나 실제 열지 않은 사진의 성능을 주장하지 않는다.

설명은 고1 학생이 이해할 한국어로 하며, 먼저 작동하는 작은 변경부터 만들고 확장하라.
완료 보고: 무엇을 바꿨는지, 연결 규격 유지 여부, 실제 검사, 남은 제한, 브랜치·커밋·PR.

---

# 공통 규격 v1 — 세 Codex가 같은 이름으로 연결할 기준

실제 자료형은 `shared/contracts.py`와 `core/models.py`에 있다. 문서와 코드가 다르면 임의 추측하지 말고 C가 일치시킨다.
JSON 키는 아래 영문 그대로 사용한다. 한국어 표시명은 UI에서만 붙인다.

## 공개 함수

| 호출 | 입력 | 출력 | 실패 |
| --- | --- | --- | --- |
| A `features.recognition.recognize_photo` | `data: bytes`, `filename: str`, 키워드 `engine: OCREngine`, 선택 `progress: Callable[[str], None]` | `ScanOutput(result: IngredientScan, image: PIL.Image)` | 파일 문제 ValueError, 모델·인식 실패는 result.status |
| A `features.recognition.prepare_review` | `text: str` | `tuple[IngredientDraft, ...]` | 빈 입력은 빈 tuple, 자료 손상 ValueError/OSError |
| B `features.analysis.analyze_confirmed` | `AnalysisRequest(ingredients: tuple[ConfirmedIngredient, ...], mode="count")` | `AnalysisResult` | 잘못된 함량 ValueError, 빈 목록 status=no_data |

C는 A의 공개 함수만 사용해 입력·후보를 얻고, 확인 후 B의 공개 함수를 호출한다.
A·B는 Streamlit·ui를 import하지 않는다. A가 B를, B가 A의 서비스 모듈을 호출하지 않는다.
core의 공통 자료형·정규화 도구를 재사용하는 것은 가능하다.

## 이름과 값

| 이름 | 형식·의미 |
| --- | --- |
| `raw_text` | 수정 전 문자열. 사용자 편집으로 덮지 않는다 |
| `name` | 제안명(초안) 또는 사용자가 확정한 성분명(ConfirmedIngredient). 어느 자료형인지 구별 |
| `original_fragment` | 분리 전 OCR 조각. 원문 전체는 IngredientScan.ocr.raw_text에 남음 |
| `cleaned_text`, `normalized` | 검색용 서식 정리 문자열, 공백·대소문자 등을 정리한 검색 키. 원문과 다름 |
| `bbox` | 점 네 개의 tuple. 해당 OCR 경로 입력 영상 픽셀 좌표. 원본 좌표라고 가정 금지 |
| `confidence` | OCR 내부 0~1 점수. 정답 확률 아님 |
| `source_indices` | 원래 OCR 영역 번호 tuple. 문자별 좌표 아님 |
| `transformations` | 정리·분리·교정 과정을 설명하는 문자열 tuple |
| `candidates` | 최대 3개 Candidate(name, matched_name, method, score) |
| `method` | exact / alias / fuzzy. 문자열 유사도 score 0~100 |
| `score_gap` | 1·2위 차이 또는 None. 대조 MatchResult에 보존 |
| `confirmed` | 초안은 항상 False. 최종 버튼에서만 ConfirmedIngredient 생성 |
| `origin` | 석유계 / 식물성 / 기타 / 확인 필요. 코드에서도 이 네 문자열 사용 |
| `uncertainty_reason` | 빈 문자열 또는 db_missing / name_unresolved / origin_uncertain / evidence_insufficient |
| `amount` | 공개 함량 float 또는 None. None은 미공개, 0과 다름 |
| `unit`, `basis` | 함량 계산은 %와 mass 또는 volume. 혼합 금지 |
| `source_url`, `checked_on` | HTTPS 근거 URL, YYYY-MM-DD 확인일. 최신 규제 보증과 다름 |

OCR 상태: ready(모델 준비), ok, empty, region_not_found, dependency_error, model_error, execution_error.
초안 상태: exact, alias, correction_proposed, ai_reread_proposed, needs_review, unmatched.
후보 검색 상태: exact, alias, fuzzy, tie, ambiguous, no_candidates.
분석 상태: complete, no_data. 서로 다른 단계의 status를 한 종류로 섞지 않는다.

예: `]정 제 수`는 원문을 남기고 제안명 `정제수`, status=exact, confirmed=False로 전달한다.
`1,3-헥산다이올`을 `1,2-헥산다이올`로 자동 확정하지 않는다.

## 결과

`AnalysisResult.rows`의 `canonical_name`, `origin`, `reason`, `uncertainty_reason`, `functions`,
`source_url`, `checked_on`을 표에 쓴다. `count_ratio.values`를 그래프에도 그대로 쓴다.
`count_ratio.denominator`는 중복 제외 성분 수이며 확인 필요도 포함한다.
`count_ratio.label="성분명 개수 기준 비율"`. 함량은 추정하지 않는다.
`mode=count/partial/full`, `amount_ratio`의 공개분·미공개 계산은 core/ratio.py를 따른다.
첫 화면 기본은 count이며 함량 입력 UI는 아직 없다. 부분/전체 함량 서비스 API만 준비돼 있다.
`cautions`는 성분명별 주의 tuple. 빈 주의 목록은 안전 판정이 아니다.
대체 성분·제품 추천의 공개 API는 아직 없다. B가 근거 자료를 확보하고 C와 규격을 먼저 추가한다.

## C 세션 상태

`shared/contracts.py:SESSION_DEFAULTS`가 기준이다.
`source_key`(파일 내용·파일명·DB 지문·파이프라인 버전·재시도번호의 해시), `source_error`(사진 처리 오류 또는 None),
`scan_output`, `stage`, `input_text`, `retry_nonce`, `review_signature`, `result`를 쓴다.
`selection_key`는 검토 문자열·선택 후보 지문이다.
stage: idle / recognizing / review / complete / error.
사진·DB·입력·후보 변경 즉시 result를 None으로 만들고 재확인을 요구한다.
공유 모델은 `st.cache_resource`, 사용자 사진·목록·결과는 session_state에만 저장한다.
성분 목록 재검토와 다운로드 때문에 페이지가 다시 실행돼도 같은 사진의 OCR을 재실행하지 않는다.

## 규격 변경

C가 CONTRACT_VERSION을 올리고 이전 호출을 위한 어댑터·검사를 먼저 넣는다.
함수 이름·인자·필드·enum·CSV 열·의존성 변경은 공통 변경이다.
규격이 같다는 이유만으로 충돌이나 동작 오류가 사라지지는 않는다. 각 역할 검사와 통합 검사를 모두 통과해야 한다.

---

# 역할과 브랜치

| 역할 | 브랜치 | 담당 경로 |
| --- | --- | --- |
| A 입력·인식 | `feature/a-recognition` | `features/recognition.py`, `core/image_input.py`, `core/ocr.py`, `core/lstm_ocr.py`, `core/auto_preprocess.py`, `core/scan.py`, `core/word_refine.py`, `core/ingredient_text.py`, `core/normalize.py`, `core/match.py`, `tests/test_a_*.py`, `tests/test_ocr_postprocess.py`, `tests/fixtures/`, `docs/a/` |
| B 분석·자료·추천 | `feature/b-analysis` | `features/analysis.py`, `core/analysis.py`, `core/classify.py`, `core/ratio.py`, `core/caution.py`, 향후 추가할 `core/recommend.py`, `data/`, `scripts/build_ingredient_data.py`, `tests/test_b_*.py`, `docs/b/` |
| C Web·통합 | `feature/c-web` | `app.py`, `ui/`, `tests/test_c_*.py`, 배포·화면·공통 파일 |

C가 모아 관리하는 공통 파일: `shared/`, `core/models.py`, `core/database.py`, `config.toml`,
`requirements*.txt`, `*.bat`, `scripts/prepare_ocr.py`, `scripts/check_*.py`,
`scripts/bootstrap_branches.py`, `.github/`, `.gitignore`, `.gitattributes`, `pytest.ini`,
`AGENTS.md`, `README.md`, `docs/CONTRACTS.md`, 이 문서, `prompts/`.
자료의 내용은 B, DB 로더의 규격은 C가 담당한다. normalize.py는 A가 담당하지만
검색 키의 의미를 바꾸면 B 분석에도 영향을 주므로 공통 변경으로 조정한다.

공유 변경이 필요하면 각자 `docs/changes/A-제목.md`, `B-제목.md`, `C-제목.md`를 만든다.
같은 요청 문서를 동시에 수정하지 않는다. C는 하위 호환 어댑터와 검사부터 추가하고 main에 통합한다.
A·B는 새 main을 병합한 후 새로운 규격을 사용한다. 문서 전달만으로 다른 Codex가 변경을 알았다고 가정하지 않는다.

세 작업은 각기 다른 Codex 클라우드 체크아웃 또는 서로 다른 로컬 clone에서 실행한다.
공유 폴더 하나에서 세 Codex가 동시에 `git switch`하지 않는다.
다른 파일을 바꿔도 같은 원격 브랜치에 푸시하면 거절될 수 있다. 브랜치는 충돌을 줄이는 분리 수단이며 자동 통합 기능이 아니다.

시작: `git fetch origin` → `git status` → 자기 브랜치 선택 → clean이면 `git merge origin/main`.
마무리: 검사 → 담당 파일만 add → commit → 자기 브랜치 push → main 대상 PR.
push가 거절되면 fetch 후 자기 원격 브랜치 변경을 병합하고 검사한다. force push로 해결하지 않는다.
main 통합 후 다음 작업에서도 다시 main을 병합한다. 계약 변경이 없다면 A·B·C PR 순서는 자유다.

---

# 학생 A: 입력·인식 담당

공통 프롬프트와 AGENTS.md를 따른다. 너는 A를 돕는 Codex다.
브랜치: feature/a-recognition. 담당 경로는 docs/OWNERSHIP.md의 A 행이다.

목표는 휴대폰 화장품 성분표를 사람이 자르지 않아도 읽고, 성분 하나씩 신뢰할 수 있게 검토하도록 만드는 것이다.
features/recognition.py의 recognize_photo와 prepare_review의 이름·인자·반환형을 유지한다.
core의 기존 엔진은 개선할 때 참고하되 UI·B 분석 코드를 함께 재작성하지 않는다.

기존 구현 방식:
- Pillow/pillow-heif로 실제 포맷·10MB·2천만 화소·EXIF·MPO·HEIF를 검사한다. .jpg 이름의 HEIF도 처리한다.
- EasyOCR/CRAFT로 방향·글자·전성분 영역을 탐색하고, 원본 해상도에서 자동 자르기·기울기·확대·조명 보정을 한다.
- 로컬 Tesseract LSTM으로 두 보정 경로를 재인식하고, 불확실한 단어 픽셀을 제한된 횟수로 다시 읽는다.
- 물리적 줄과 실제 성분 항목을 구별하고, 누락 쉼표는 전체 이름을 덮는 사전 조합일 때만 분리 제안한다.
- `]정 제 수`, `[전 성 분]`, 보이지 않는 문자, 하이픈 차이를 정리한다. 원문·변환 기록은 유지한다.
- 정식명→별칭→RapidFuzz 최대 세 후보. 근접 후보·동점·숫자 차이를 사용자 검토 대상으로 남긴다.

먼저 현재 코드와 회귀 검사를 실행하고 학생이 원하는 첫 개선을 작은 단위로 구현하라.
현재 실제 사진을 제공받지 않았다면 촬영 사진 성능을 주장하지 말고 기존 회귀 라벨부터 검사하라.
새 촬영 사례를 받으면 원본 정답 목록을 따로 정리하고 이름 단위 precision/recall과 시간·누락을 비교하라.
깨끗한 인공 이미지나 손으로 옮긴 텍스트만으로 일반 정확도를 주장하지 않는다.
숫자가 다른 INCI, 알 수 없는 원료, 괄호 주석을 가까운 이름으로 강제 변환하지 않는다.

검사: python -m pytest -q tests/test_a_recognition.py tests/test_ocr_postprocess.py,
전체 python -m pytest -q, 모델 준비 후 python -m scripts.check_auto_ocr.
모델 실패·빈 결과·영역 미탐지와 DB 미등록을 구별한다.
새 의존성/공통 규격이 필요하면 C에게 변경 문서를 남긴다.
자기 브랜치에 커밋·푸시하고 PR에 전후 사례·검증 한계·화면에 전달하는 상태를 적어라.

---

# 학생 B: 분석·자료·추천 담당

공통 프롬프트와 AGENTS.md를 따른다. 너는 B를 돕는 Codex다.
브랜치: feature/b-analysis. 담당 경로는 docs/OWNERSHIP.md의 B 행이다.

features/analysis.py의 analyze_confirmed(AnalysisRequest)->AnalysisResult를 유지한다.
화면이나 OCR 모델을 호출하지 않고 C가 넘긴 사용자 확정 목록만 분석한다.
현재 core.analysis/classify/ratio/caution과 data/가 작동하는 참고 기반이다.

DB 현황: data/ingredients.csv 대표 270개, ingredient_names.csv 이름 전용 28,077개,
curation.csv 한글 매핑, source_evidence.csv 원문 근거, sources.json 출처·체크섬·집계,
licenses/ 및 NOTICE.md 재배포 고지. DB 서버 없이 CSV로 시작한다.
자료 추가 시 근거·확인일·중복 별칭·동일 INCI를 검사하고 생성 스크립트와 집계를 함께 맞춘다.
기존 2019 근거와 새로 검토한 현재 근거의 시점·범위를 구별한다. 사전 등재만으로 유래·허용·안전성을 주장하지 않는다.

유래는 석유계/식물성/기타/확인 필요다. 제조 유래가 다른 글리세린 등을 이름만으로 식물성으로 정하지 않는다.
DB 미등록·미확정 이름·유래 불명·근거 부족을 구별하고, 개수 비율에는 모두 포함한다.
성분명 중복은 canonical_name으로 제거하지만 원본 기록을 보존한다. 중복 함량이 다르면 오류다.
일부 공개 함량은 미공개를 따로 표시한다. 전체 공개는 동일 단위·기준·합계 100%를 검사한다.

현재 주의 DB는 FDA 인체 주의 27개 물질과 PubChem/HSDB 환경 시험 3개 물질(표기별 63행)을 포함한다. 대체 성분·제품 CSV는 헤더만 있다. 대체·제품 추천 엔진은 아직 없다.
새 추천을 구현한다면 원문 근거와 기능·적용 제품·국가·농도·검토 날짜를 확인하고 B→C 결과 규격부터 추가한다.
단순 기능 태그 중첩은 참고 후보일 뿐 실제 처방 대체·안전성·동등 효능 보증이 아니다.
가격·구매 링크·최신 법령·알레르기 정보를 만들어내지 않는다. 자료가 없으면 빈 결과와 이유를 반환한다.
UI에 무슨 카드를 보여줄지는 C의 책임이다.

먼저 현재 분석·자료 검사를 돌리고 학생이 원하는 작은 DB 확충 또는 분석 개선부터 구현하라.
tests/test_b_*.py에 정상·미등록·중복·빈 목록·잘못된 함량·자료 없음 사례를 검사한다.
기존 역할 검사는 `python -m pytest -q tests/test_b_analysis.py`로 실행한다.
전체 pytest와 서버 검사를 실행하고 자기 브랜치에 커밋·푸시·PR을 만든다.
PR에는 출처·자료 시점·규격 영향·모르는 상태를 어떻게 남겼는지 기록한다.

---

# 학생 C: 웹·통합 담당

공통 프롬프트와 AGENTS.md를 따른다. 너는 C를 돕는 Codex다.
브랜치: feature/c-web. 담당 경로와 공통 파일 목록은 docs/OWNERSHIP.md를 따른다.

목표는 사용자에게 바로 보여줄 한국어 서비스다. 기존 교사 예시 UI를 복사하지 말고 학생이 고른
서비스 이름·레이아웃·설명·스타일을 구현하라. 현재 app.py/ui/site.py는 작동 여부를 위한 작은 시작점이다.
가상 예제, 계산 연습, DB 모드, 수동 자르기·대비 옵션, 사용자가 판단할 필요 없는 기술 옵션을 노출하지 않는다.

사진을 올리면 A recognize_photo를 자동 실행하고 영역·회전·전처리·OCR·후보를 한 흐름으로 처리한다.
같은 사진으로 화면이 다시 실행될 때 OCR을 반복하지 않는다. 모델/DB만 공유 캐시한다.
명확한 성분은 목록에 정리하고 불확실한 성분만 원문·후보와 함께 수정하게 한다.
후보를 선택할 때마다 적용 버튼을 요구하지 않는다. 최종 목록 확인 버튼 한 번으로 B 분석과 결과 표시가 이어져야 한다.
사진·입력·후보·DB 변경 시 이전 분석·그래프·주의·추천을 즉시 지운다. 실패 후 재시도·직접 입력도 제공한다.

B의 동일 AnalysisResult로 표·그래프·주의를 표시한다. UI에서 별도 분류·비율을 다시 계산하지 않는다.
확인 필요와 근거를 숨기지 않으며 개수 비율을 배합 함량처럼 표시하지 않는다.
빈 주의 DB를 안전함으로 표현하지 않는다. 추천 API가 아직 없다는 사실을 지킨다.
원문·변환 과정은 필요한 사용자만 펼쳐 보게 하고 화면 기본 흐름은 짧게 유지한다.
사진 원본은 외부 AI로 전송하지 않으며 서버 로그·공용 캐시에 남기지 않는다.

C는 shared/contracts.py, core/models.py, core/database.py와 환경·공통 문서를 모아 관리한다.
A/B의 공통 변경 요청은 호환 어댑터·버전·검사부터 구현해 main에 공유하고 두 역할이 main을 병합하도록 한다.
branch가 자동 최신화되거나 다른 Codex가 현재 대화를 공유한다고 가정하지 않는다.
통합은 prompts/INTEGRATE.md를 따른다. 맡지 않은 A/B 내부 로직을 디자인 변경에 끼워 넣지 않는다.

검사: tests/test_c_*.py에서 최초 화면·자동 인식·확정 전 미분석·한 번 확인·입력/후보/사진 변경 무효화·오류/재시도·세션 분리를 확인한다.
기존 역할 검사는 `python -m pytest -q tests/test_c_site.py tests/test_c_branches.py`로 실행한다.
전체 pytest, 서버 검사, OCR 연결을 실행한다. 실제 Windows 검사는 workflow 결과와 구별한다.
로컬 실행은 공개 배포가 아니다. 공개 배포 요청이 있으면 학생이 고른 호스팅에서 CPU OCR 자원·모델 준비·HTTPS·사진 보존 방침을 확인한다.
학생이 원한 작업을 구현하고 검증한 뒤 자기 브랜치에 커밋·푸시·PR을 만들고 통합 상태를 정확히 보고한다.

---

# C에게 전달: 세 역할의 변경 통합

AGENTS.md와 공통 규격을 지키면서 지금 준비된 A/B/C 변경을 새 프로젝트 main에 통합하라.
먼저 origin URL, 현재 branch/status, 원격 main과 각 작업 브랜치를 fetch하고 변경 내용을 읽어라.
로컬 사용자 변경을 덮거나 자동 stash하지 말고 보존하라. 미완료 PR을 완료됐다고 가정하지 마라.

1. PR별 담당 파일·공통 필드·함수 시그니처·CSV 변경·출처·의존성을 검토한다.
2. 규격 변경이 있으면 C가 호환 어댑터·문서·계약 버전·검사를 먼저 반영한다.
3. 최신 origin/main에서 별도 임시 통합 브랜치/체크아웃을 만들고 선택한 변경을 차례로 병합한다.
   같은 파일 충돌뿐 아니라 함수 이름·상태·변수·UI 의미 충돌도 확인한다. 임의 한쪽 전체 선택으로 해결하지 않는다.
4. 전체 pytest, Streamlit 서버 검사, 실제 CPU OCR 연결 검사를 실행한다.
   업로드→자동 인식→후보 선택→최종 확인 한 번→같은 목록의 표·그래프·주의를 검사한다.
   사진·입력·후보·DB 변경 시 오래된 결과가 사라지는지도 확인한다.
5. 실패를 수정하고 재검사한다. 원격 main이 더 진행됐다면 다시 병합·검사한다. force push하지 않는다.
6. 저장소 권한·보호 규칙에 맞춰 검증한 PR을 병합한다. 병합 권한이 없으면 검증한 커밋·PR·남은 권한을 보고한다.
7. A/B/C 작업 브랜치가 main을 자동으로 포함했다고 말하지 말고 다음 작업 시작 때 origin/main 병합을 안내한다.

결과에는 합친 PR/커밋, 공통 규격 변경 여부, 실제 검사 환경·결과, 남은 제한만 간결히 적어라.

현재 자료 확장 안내(2026-10-30): 기존 270/28,077은 원본 파일 구성이다. KCIA 공개 명칭22,021행·정의144개 검토를 연결한 현재 통합은32,797개(검토394 / 이름전용32,403), 정확 검색키57,706개다. 회원사 전용 유래 자료는 접근하지 않았다. data/kcia_sources.json·data/README.md를 기준으로 하고 화학명만으로 유래를 추정하지 않는다.
