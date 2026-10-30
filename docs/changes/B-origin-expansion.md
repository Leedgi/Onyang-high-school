# 유래 근거 확장 v1 — C 통합 요청

입력: 기존 열과 같은 origin_ingredients.csv, origin_sources.json, 검토 입력 origin_review/origin_route_review.json. 처리: 기본/KCIA 체크섬 및 확장 체크섬 검증 뒤 정식명 기준으로만 교체, 원래 별칭은 유지. 기존 origin=확인 필요인 항목만 변경하고 기존 확정 유래 변경은 거부한다. 출력: 같은 IngredientDatabase/AnalysisResult. 실패: 불일치·충돌은 오류 및 이전 결과/PDF 제거.

5,749개를 규칙 대조로 추가 분류(식물5,504/석유11/기타234). 규칙 기반 대조와 개별 수동 검토를 화면/문서에서 구분한다. 2019 스냅샷을 최신 검토로 표현하지 않는다. 제조 경로 참고5개는 기존 reason의 [제조 경로 참고] 접두사로 호환 전달하고 origin_uncertain을 유지한다. C는 같은 AnalysisResult.rows.reason을 펼침 안내로 표시할 수 있다. 후보 경로를 확정 그래프 비율에 섞지 않는다. 공개 함수/모델/enum은 유지한다.
