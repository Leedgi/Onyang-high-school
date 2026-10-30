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

주의 DB는 FDA 인체 주의 27개 물질과 PubChem/HSDB 환경 시험 3개 물질(표기별 63행)을 포함한다. data/reviewed/caution_review.json을 검토 입력으로 python -m scripts.build_caution_data로 재생성한다. 대체 성분·제품 CSV는 헤더만 있다. 대체·제품 추천 엔진은 아직 없다.
새 추천을 구현한다면 원문 근거와 기능·적용 제품·국가·농도·검토 날짜를 확인하고 B→C 결과 규격부터 추가한다.
단순 기능 태그 중첩은 참고 후보일 뿐 실제 처방 대체·안전성·동등 효능 보증이 아니다.
가격·구매 링크·최신 법령·알레르기 정보를 만들어내지 않는다. 자료가 없으면 빈 결과와 이유를 반환한다.
UI에 무슨 카드를 보여줄지는 C의 책임이다.

먼저 현재 분석·자료 검사를 돌리고 학생이 원하는 작은 DB 확충 또는 분석 개선부터 구현하라.
tests/test_b_*.py에 정상·미등록·중복·빈 목록·잘못된 함량·자료 없음 사례를 검사한다.
기존 역할 검사는 `python -m pytest -q tests/test_b_analysis.py`로 실행한다.
전체 pytest와 서버 검사를 실행하고 자기 브랜치에 커밋·푸시·PR을 만든다.
PR에는 출처·자료 시점·규격 영향·모르는 상태를 어떻게 남겼는지 기록한다.

현재 자료 확장 안내(2026-10-30): 기존 270/28,077은 원본 파일 구성이다. KCIA 공개 명칭22,021행·정의144개 검토를 연결한 현재 통합은32,797개(개별검토·정의규칙대조6,143 / 이름전용26,654), 정확 검색키57,706개다. 회원사 전용 유래 자료는 접근하지 않았다. data/kcia_sources.json·data/README.md를 기준으로 하고 화학명만으로 유래를 추정하지 않는다.
