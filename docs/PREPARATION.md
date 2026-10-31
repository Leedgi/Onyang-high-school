# 학생 프로젝트 준비 결과

2026-10-25 한국 시간. Linux x86_64, Python 3.12.14, CPU에서 직접 검사했다.
실제 Windows 검사 결과는 아니다. ZIP의 기존 검증 기록과 이번 실행을 구별한다.

## 준비 범위

- 첨부 ZIP의 student-starter만 이 저장소 최상위에 배치했다. 교사 화면·가상 예제는 합치지 않았다.
- 참고 원본은 클라우드의 `/workspace/reference-materials/Ingredients-list-ai-main`과 원본 ZIP에 별도 보존했다.
- 새 프로젝트 원격은 `https://github.com/Leedgi/Onyang-high-school.git`이다. 기존 예시 원격·Git 이력·가상환경·모델 캐시·비밀값은 복사하지 않았다.
- 연결 규격 v1과 A/B/C 엔진·화면은 수정하지 않았다. 특정 학생 역할의 기능 개발은 수행하지 않았다.

## 이번 검사

- requirements.txt 설치, pip check 통과.
- 전체 pytest 31개 통과. 화면 검사는 명시적인 모의 OCR로 자동 업로드 연결, 중복 인식 방지, 최종 확인, 변경 시 결과 해제, 오류 복구, 세션 분리를 검사한다.
- scripts.check_server 통과: 실제 서버 health와 HTML 응답 확인. 저장된 시작 명령으로 서버를 따로 실행해 동일한 응답도 확인했다.
- scripts.prepare_ocr 최초 다운로드·체크섬 검사 통과. 재실행도 통과해 기존 모델 재사용을 확인했다.
- scripts.check_auto_ocr 실제 CPU 모델 실행 통과. 인공 라벨 26개 중 기존 방식 7개, 자동 OCR 이름 21개, 미확정 교정 제안 포함 24개 일치. 제안 포함 precision/recall은 이 한 장에서 각각 24/26이다. 실제 촬영 사진이나 일반 정확도를 검증한 결과가 아니다.
- 상세 인공 검사 출력은 로컬 artifacts/auto-ocr-comparison.json에 있다. 사용자 사진은 제공되지 않았다.
- CSV 확인: 대표 270개, 이름 전용 28,077개. 주의·대체·제품 CSV는 각각 0행이다.

## 실행

현재(2026-10-31) Windows 10/11 x64에서는 Python 3.14를 설치한 후 `setup_windows.bat`을 최초 한 번 실행하고, 이후에는 `run_windows.bat`을 실행한다. 의존성·모델 구성이 바뀐 때만 setup을 다시 실행한다. Linux의 .venv는 Windows로 복사하지 않는다.

Linux 클라우드에서는 저장소에서 `.venv/bin/python -m streamlit run app.py`로 실행한다. 설치된 의존성과 모델은 유지하되 새 작업에서는 서버를 다시 시작해야 한다. 공개 배포는 수행하지 않았다.

## 학생에게 전달

| 학생 | 브랜치 | 읽을 프롬프트 | 첫 작은 작업 제안 |
| --- | --- | --- | --- |
| A 입력·인식 | feature/a-recognition | prompts/00_COMMON.md + prompts/A.md | 인공 라벨에서 틀린 두 이름의 원문·후보를 비교하고, 숫자 보존 회귀 사례 하나를 개선 대상으로 선택 |
| B 분석·자료 | feature/b-analysis | prompts/00_COMMON.md + prompts/B.md | 확인 필요 성분 하나의 현재 원문 근거를 검토하고 출처·확인일을 갖춘 자료 보완 제안 |
| C 웹·통합 | feature/c-web | prompts/00_COMMON.md + prompts/C.md | 학생이 선택한 서비스 이름과 첫 화면 설명을 반영하고 한 번 확인 흐름을 검사 |

세 학생은 각각 독립된 Codex 작업 체크아웃 또는 별도 로컬 clone을 사용한다. 한 폴더에서 동시에 git switch하지 않는다. 브랜치는 자동 동기화되지 않는다. 시작 때 fetch/status를 확인하고 clean 상태에서 origin/main을 자기 브랜치에 병합한다. 공통 변경은 C가 규격·호환 검사와 함께 반영한다.

## 남은 범위

서비스 이름·디자인·학생별 개선은 아직 선택하지 않았다. 실제 촬영 사진 평가, 실제 Windows 실행 검증, 근거 있는 주의·추천·제품 데이터와 추천 공개 API, 공개 배포는 남아 있다. 빈 주의 자료를 안전 판정으로 해석하지 않는다. 성분명 개수 비율은 함량이 아니며, 2019 이름 자료는 최신 규제·안전성 근거가 아니다.
