# 역할과 브랜치

| 역할 | 브랜치 | 담당 경로 |
| --- | --- | --- |
| A 입력·인식 | `feature/a-recognition` | `features/recognition.py`, `core/image_input.py`, `core/ocr.py`, `core/lstm_ocr.py`, `core/auto_preprocess.py`, `core/scan.py`, `core/word_refine.py`, `core/ingredient_text.py`, `core/normalize.py`, `core/match.py`, `tests/test_a_*.py`, `tests/test_ocr_postprocess.py`, `tests/fixtures/`, `docs/a/` |
| B 분석·자료·추천 | `feature/b-analysis` | `features/analysis.py`, `core/analysis.py`, `core/classify.py`, `core/ratio.py`, `core/caution.py`, 향후 추가할 `core/recommend.py`, `data/`, `scripts/build_ingredient_data.py`, `scripts/build_caution_data.py`, `scripts/build_kcia_data.py`, `scripts/import_kcia_names.py`, `tests/test_b_*.py`, `docs/b/` |
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
