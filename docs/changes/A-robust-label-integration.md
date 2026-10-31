# A 인식 개선 C 통합 요청

공개 recognize_photo/prepare_review 함수·인자/반환형, enum, CSV는 유지한다. 내부 OCREngine/LSTMReader에 단일 행 판독을 추가하고 scan 내부 경로 버전을6으로 올렸다. 원문·슬래시·숫자·nano 주석을 정규화에서 지우지 않는다. 박스 좌표계와 행 변환 정보는 ScanOutput의 기존 processing/passes에 보존한다.

C는 PIPELINE_VERSION을 올려 이전 같은 사진 결과를 무효화한다. 자동 인식의 correction_proposed/ai_reread_proposed/needs_review 상태는 input_text에 제안명을 넣었다는 이유로 prepare_review의 exact 상태로 덮지 말아야 한다. 원본 인식 후 자동 입력 그대로인 동안 A의 미확정 초안을 유지해 원문과 후보를 보여주고 최종 버튼에서만 ConfirmedIngredient를 만든다. 사용자가 목록 자체를 수정하면 기존 prepare_review 흐름을 쓴다.

추가 의존성·모델 설치는 없다. 전체81개 검사와 서버 검사, 실제 CPU 방향/기하 합성 시험을 구분해 검증한다. 통합에서는 실제 Windows CPU에서 180도·곡면·후처리 연결을 검사하며 인공 라벨 결과를 실제 촬영 사진 정확도로 바꾸지 않는다.
