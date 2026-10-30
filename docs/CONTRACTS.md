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


## 별도 주의 자료의 선택적 확장 (2026-10-30)

공개 함수·자료형·기존 CSV 열과 CONTRACT_VERSION=1은 유지한다. 새 자료는 선택적 파일 형식 v1이다.
`caution_aliases.csv`의 alias,inci,source_url,checked_on,source_cas를 검증해 기존 INCI 레코드에 동의어를 추가한다. 다른 성분과 충돌하면 오류이며 이름 전용 레코드의 유래는 확인 필요 그대로다. 파일이 없는 기존 프로젝트는 기존 동작을 유지한다.
`caution_sources.json`은 주의·별칭·환경 시험 CSV의 SHA-256을 집계한다. 있을 때 로더가 생성물의 일치를 검증한다. 주의·별칭·환경 근거·검토 입력이 바뀌면 DB 지문도 바뀌어 재확인을 요구한다.
기존 CautionRecord.reason의 `[인체·...]` / `[환경·생분해성]` 접두사는 화면 묶음 표시만 위한 후방 호환 어댑터다. 접두사가 없는 기존 레코드도 ‘그 밖의 등록 주의’로 표시한다. severity·pH·생분해 등급 필드를 새로 만들지 않는다. 농도·제품·국가·사용 조건·원문·확인일은 기존 필드를 그대로 보존한다.


## KCIA 선택적 명칭/정의 확장 v1 및 OCR 캐시 (2026-10-30)

함수·자료형·enum·기존 CSV 열과 CONTRACT_VERSION=1을 유지한다. kcia_ingredients.csv는 기존 IngredientRecord 열 그대로이며 kcia_sources.json의 고정 파일·기본 DB 체크섬과 병합 집계가 일치할 때만 적용한다. 기존 정식명은 교체하고 새 정식명은 추가하며 최종 별칭 충돌은 실패다. 별칭 충돌242건은 생성 단계에서 격리해 자동 병합하지 않았다. 확장이 없는 기존 프로젝트는 기존 로딩을 유지한다.

기존 기본 사전270+28,077은 보존한다. 공개 표준 명칭22,021행 중 중복을 제외한 통합32,797개, 정확 키57,706개다. definition_reviewed 항목은 기존 uncertainty_reason으로 표현한다. 공개 정의로도 공급원을 모르면 origin_uncertain, 이름 전용은 evidence_insufficient이며 둘 다 비율 분모에 포함한다. 검토394개라는 수가 모두 유래 확정을 뜻하지 않는다.

모든 확장 생성물/검토 입력은 DB 파일 지문에 포함한다. 자료 오류 시 C가 이전 result와 pdf_export를 지운다. PIPELINE_VERSION=geometry-kcia-2로 바꿔 같은 사진의 이전 OCR 결과를 재사용하지 않는다. 사진·원문·후보를 공용 캐시에 넣지 않는다. OCR 내부 경로 버전은 v5이며 공개 상태값은 바꾸지 않는다.


## 명시적 정의 유래 확장 v1 (2026-10-30)

함수/모델/CSV 열/enum/CONTRACT_VERSION은 유지한다. origin_ingredients.csv는 기존 IngredientRecord 열의 선택적 확장이다. origin_sources.json으로 기본·KCIA·확장·검토 입력 체크섬 및 병합 집계를 검증한다. 기존 origin=확인 필요인 정식명만 보완하고 별칭 변경/확정 유래의 덮어쓰기는 거부한다. 확장이 없는 자료는 이전 동작을 유지한다. 파일 변경은 DB 지문에 반영되고 오류는 이전 result/pdf_export를 지운다.

제조 경로가 여러 개인 항목은 기존 reason의 [제조 경로 참고] 접두사로 설명하며 origin_uncertain을 유지한다. C는 같은 AnalysisResult.rows의 이유를 펼쳐 표시하고 PDF에도 보존한다. 후보 제조 경로를 그래프의 확정 유래에 섞거나 제품 배치 원료로 단정하지 않는다. 추가5,749개는2019 정의 규칙 대조이며 개별 최신 수동 검토와 구분한다. 현재 통합32,797개, 개별검토/정의규칙근거6,143개, 이름전용26,654개다.
