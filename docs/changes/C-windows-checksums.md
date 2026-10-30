# Windows 체크섬 검사 수정

Windows run 41065639658은 설치에는 성공했지만 데이터 체크섬 불일치로 pytest 50개가 실패하여 실제 CPU OCR까지 진행하지 못했다. Git autocrlf가 CSV/JSON을 CRLF로 바꾸는 것이 원인이었다. .gitattributes에서 CSV/JSON을 LF로 고정한다. SHA-256 검사를 끄거나 다른 자료의 체크섬으로 덮어쓰지 않는다. Windows용 bat은 CRLF 그대로 유지한다. 새 Windows 실행 결과는 workflow에서 별도로 확인한다.
