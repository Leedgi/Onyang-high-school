# 자료 출처 표시

## Cosmetic Ingredients Dataset (Lite)

Copyright (c) 2025 BEAUTEE.

https://beautee.ru/

Repository: https://github.com/beauteeru/cosmetic-ingredients-dataset

Snapshot commit: `ad1d9afad3f1a721873878b83fbd9f674d628c9e`

License: MIT. 원문은 [BEAUTEE-MIT.txt](licenses/BEAUTEE-MIT.txt)에 보존했다.
`ingredient_names.csv`는 이름·식별자에서 중복을 제외한 자료다.
원 제공자가 이 프로젝트의 분류·안전성을 검증·보증했다는 뜻이 아니다.

## CosIng database finder

Repository: https://github.com/walkowskis/CosIng_database_finder

Snapshot commit: `d3dbd5644813ef6c1bff59b6b075fec54a1eaaff` (2019-03-16)

공개 SQLite에서 선택 성분 정의·기능·참조 번호를 조회한 사실 자료를 사용했다.
원본 SQLite 전체나 규제·제한 목록은 이 저장소에 재배포하지 않는다.
`source_evidence.csv`는 선택한 명칭·정의·기능의 근거이며,
공식 CosIng 서비스나 최신 규정에 대한 검증·인증을 뜻하지 않는다.


## 별도 주의 자료

FDA: https://www.fda.gov/cosmetics/cosmetic-ingredients/alpha-hydroxy-acids , https://www.fda.gov/cosmetics/cosmetic-ingredients/beta-hydroxy-acids , https://www.fda.gov/cosmetics/cosmetic-ingredients/allergens-cosmetics . 미국 정부의 소비자 안내에서 확인한 사실을 한국어로 요약했다. 자료의 날짜와 확인일을 구분하며 FDA가 이 서비스를 인증했다는 뜻이 아니다.

환경 시험: NIH/NLM PubChem의 D4(CID 11169), D5(CID 10913), D6(CID 10911) `Environmental Biodegradation` 항목에서 HSDB의 물질별 시험 사실을 확인했다. 원 제공자·논문·ECHA/캐나다 평가서 인용 정보를 `reviewed/caution_review.json`에 남겼다. PubChem 전체를 단일 라이선스로 재배포하거나 원 저자의 논문 전문을 복제하지 않는다. 제공자 정책: https://www.nlm.nih.gov/web_policies.html . 물질별 시험 사실의 요약과 필요한 짧은 인용만 보존한다.

명칭 대조: 대한화장품협회 성분사전 https://kcia.or.kr/cid/search/ingd_list.php 의 선택한 29개 INCI 검색 결과에서 이름·CAS를 확인했다. 선택한 표기 연결만 사용하고 사전 전체·사이트 코드·이미지는 재배포하지 않는다. 명칭 등재가 안전성·유래·국가별 사용 허용의 증거가 아니다.
