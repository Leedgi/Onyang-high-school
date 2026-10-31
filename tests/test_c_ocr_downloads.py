import hashlib
from io import BytesIO
from pathlib import Path
import socket
import ssl
import subprocess
from types import SimpleNamespace
from urllib.error import URLError
from zipfile import ZipFile

import pytest
from scripts import ocr_downloads as downloads
from scripts import prepare_ocr


def model(payload=b'validated model',member=None):
    return downloads.Model('검사 모델','model/test.pth','https://example.invalid/model.zip',
                           hashlib.sha256(payload).hexdigest(),member)


def test_verified_cache_never_contacts_network(tmp_path,monkeypatch):
    spec=model();target=tmp_path/spec.relative_path;target.parent.mkdir();target.write_bytes(b'validated model')
    monkeypatch.setattr(downloads,'download',lambda *a:pytest.fail('기존 검증 파일을 다시 다운로드함'))
    downloads.ensure_model(tmp_path,spec)


def test_bad_download_does_not_replace_existing_model_and_removes_temporary_files(tmp_path,monkeypatch):
    spec=model();target=tmp_path/spec.relative_path;target.parent.mkdir();target.write_bytes(b'old model')
    monkeypatch.setattr(downloads,'download',lambda url,path,emit:path.write_bytes(b'invalid response'))
    with pytest.raises(ValueError,match='SHA-256'):downloads.ensure_model(tmp_path,spec)
    assert target.read_bytes()==b'old model'
    assert list(target.parent.iterdir())==[target]


def test_temporary_url_error_is_retried(tmp_path,monkeypatch):
    attempts=[]
    def request(url,path):
        attempts.append(url)
        if len(attempts)==1:raise URLError(TimeoutError('timed out'))
        path.write_bytes(b'validated model')
    monkeypatch.setattr(downloads,'_python_download',request)
    monkeypatch.setattr(downloads.time,'sleep',lambda _:None)
    downloads.ensure_model(tmp_path,model())
    assert len(attempts)==2


def test_native_windows_retry_keeps_tls_and_content_verification(tmp_path,monkeypatch):
    def failed(*args):raise URLError(ssl.SSLCertVerificationError('CERTIFICATE_VERIFY_FAILED'))
    calls=[]
    def curl(args,**kwargs):
        calls.append(args);Path(args[args.index('--output')+1]).write_bytes(b'validated model')
        return subprocess.CompletedProcess(args,0,b'',b'')
    monkeypatch.setattr(downloads,'_python_download',failed)
    monkeypatch.setattr(downloads,'_curl_executable',lambda:'native-curl.exe')
    monkeypatch.setattr(downloads.subprocess,'run',curl)
    monkeypatch.setattr(downloads.time,'sleep',lambda _:None)
    downloads.ensure_model(tmp_path,model())
    assert len(calls)==1
    args=calls[0]
    assert '--insecure' not in args and '-k' not in args
    assert args[args.index('--proto')+1]=='=https'
    assert args[args.index('--proto-redir')+1]=='=https'
    assert (tmp_path/'model/test.pth').read_bytes()==b'validated model'


def test_only_the_pinned_zip_member_is_installed(tmp_path,monkeypatch):
    archive=BytesIO()
    with ZipFile(archive,'w') as z:
        z.writestr('test.pth',b'validated model');z.writestr('../unexpected.txt',b'never extract')
    monkeypatch.setattr(downloads,'download',lambda url,path,emit:path.write_bytes(archive.getvalue()))
    downloads.ensure_model(tmp_path,model(member='test.pth'))
    assert (tmp_path/'model/test.pth').read_bytes()==b'validated model'
    assert list(tmp_path.rglob('*'))==[tmp_path/'model',tmp_path/'model/test.pth']


def test_actual_network_reason_is_saved_without_url_credentials(tmp_path,monkeypatch):
    monkeypatch.setattr(prepare_ocr,'ROOT',tmp_path)
    monkeypatch.setattr(prepare_ocr.importlib,'import_module',lambda name:SimpleNamespace(__version__='test'))
    def failed(*args):raise URLError(socket.gaierror(11001,'getaddrinfo failed'))
    monkeypatch.setattr(prepare_ocr,'prepare_all',failed)
    assert prepare_ocr.main()==1
    text=(tmp_path/'artifacts/ocr-setup.txt').read_text(encoding='utf-8')
    assert 'getaddrinfo failed' in text and '11001' in text
    assert '네트워크' in text and '사진' in text
    redacted=downloads.safe_error(URLError('failed https://user:secret@example.org/model?token=private'))
    assert 'secret' not in redacted and 'private' not in redacted
    assert 'example.org/model' in redacted


def test_persistent_network_failure_preserves_its_reason(tmp_path,monkeypatch):
    def failed(*args):raise URLError(ssl.SSLCertVerificationError('CERTIFICATE_VERIFY_FAILED'))
    monkeypatch.setattr(downloads,'_python_download',failed)
    monkeypatch.setattr(downloads,'_curl_executable',lambda:None)
    monkeypatch.setattr(downloads.time,'sleep',lambda _:None)
    with pytest.raises(URLError) as result:downloads.download('https://example.invalid/model',tmp_path/'file')
    assert '인증서' in downloads.guidance(result.value)
    assert 'CERTIFICATE_VERIFY_FAILED' in downloads.safe_error(result.value)
