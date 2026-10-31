"""Windows 검사 전용: Python 연결 실패를 주입하고 실제 curl HTTPS 모델 수신·해시를 확인."""
import os
from pathlib import Path
import ssl
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

from scripts.ocr_downloads import MODELS, _curl_executable, ensure_model


def main():
    if os.name!='nt':
        print('Native Windows downloader check skipped on this OS.')
        return 0
    if not _curl_executable():
        raise RuntimeError('Windows 기본 curl.exe를 찾지 못했습니다.')
    error=URLError(ssl.SSLCertVerificationError('injected Python TLS failure for recovery test'))
    with TemporaryDirectory(prefix='ocr-download-check-') as folder:
        with patch('scripts.ocr_downloads._python_download',side_effect=error):
            ensure_model(Path(folder),MODELS[-1])
    print('PASS: injected Python failure -> native Windows HTTPS download -> pinned SHA-256 verification.')
    return 0


if __name__=='__main__':raise SystemExit(main())
