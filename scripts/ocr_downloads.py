"""설치 전용: 공식 모델의 HTTPS 다운로드·제한 재시도·SHA-256 검증."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import ssl
import subprocess
from tempfile import NamedTemporaryFile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from zipfile import ZipFile


@dataclass(frozen=True)
class Model:
    name: str
    relative_path: str
    url: str
    sha256: str
    member: str | None = None


MODELS = (
    Model('글자 영역 모델', 'easyocr/model/craft_mlt_25k.pth',
          'https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip',
          '4a5efbfb48b4081100544e75e1e2b57f8de3d84f213004b14b85fd4b3748db17', 'craft_mlt_25k.pth'),
    Model('한국어·영어 이름 모델', 'easyocr/model/korean_g2.pth',
          'https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/korean_g2.zip',
          'ecdead53c909748aad74bc2f2beeab3e3ad751134db6335e97ea19f879ca407e', 'korean_g2.pth'),
    Model('한국어 인쇄 글자 모델', 'tessdata_best/kor.traineddata',
          'https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/kor.traineddata',
          'f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff'),
    Model('영어 인쇄 글자 모델', 'tessdata_best/eng.traineddata',
          'https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/eng.traineddata',
          '8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba'),
)


# 공식 배포 커밋과 파일 SHA를 고정한다. 사진은 다운로드 서버로 전송하지 않는다.
NEURAL_MODELS = (
    Model('PP-OCRv5 글자 줄 검출', 'ppocr_v5/det.onnx',
          'https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx/resolve/e6f4fa85f00e168c862bc462aebca69eef9b3d3d/inference.onnx',
          'a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d'),
    Model('PP-OCRv5 한국어 이름 인식', 'ppocr_v5/korean.onnx',
          'https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec_onnx/resolve/5c6f574b8e2230adf4287b33e736d71b9fabd28e/inference.onnx',
          '92f0b7785e64fc9090106a241cf4c1eb97472824558272751b88a2a4476d3a08'),
    Model('PP-OCRv5 한국어 문자 사전', 'ppocr_v5/korean.yml',
          'https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec_onnx/resolve/5c6f574b8e2230adf4287b33e736d71b9fabd28e/inference.yml',
          'f757fa1c40e99edcf27e9cce879b93eb2a51fa46f5ef39095689b8c37dd75998'),
)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def safe_error(exc):
    """URL 안 인증정보/쿼리나 프록시 환경 변수를 진단 파일에 남기지 않는다."""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    text = str(reason)
    def redact(match):
        try:
            u=urlsplit(match[0]);return u.scheme+'://'+(u.hostname or '[주소]')+u.path
        except ValueError:
            return '[주소 숨김]'
    return re.sub(r'https?://[^\s<>\"]+',redact,text)[:800]


def guidance(exc):
    reason=exc.reason if isinstance(exc,urllib.error.URLError) else exc
    if isinstance(reason,ssl.SSLCertVerificationError) or 'CERTIFICATE_VERIFY_FAILED' in str(reason):
        return 'HTTPS 인증서 확인 실패입니다. PC 날짜·시간과 학교/회사 네트워크의 인증서 설정을 확인해 주세요. 인증서 검증을 끄지 마세요.'
    if isinstance(exc,urllib.error.HTTPError):
        return f'다운로드 서버가 HTTP {exc.code}로 응답했습니다. 해당 네트워크의 GitHub 접근 제한·프록시 설정을 확인해 주세요.'
    if isinstance(exc,urllib.error.URLError) or isinstance(reason,(TimeoutError,ConnectionError)):
        return '다운로드 연결 실패입니다. 다른 네트워크(예: 휴대폰 핫스팟)에서 다시 시도하면 학교/회사망 제한인지 구분할 수 있습니다.'
    if isinstance(exc,PermissionError):
        return '모델 폴더에 쓸 수 없습니다. 폴더 쓰기 권한과 사용 중인 앱을 확인해 주세요.'
    return '표시된 실제 오류를 확인해 주세요. 모델 파일 검증에 실패하면 해당 파일을 사용하지 않습니다.'


def _python_download(url,path):
    request=urllib.request.Request(url,headers={'User-Agent':'Onyang-school-OCR-setup/1.0'})
    with urllib.request.urlopen(request,timeout=45) as response, path.open('wb') as output:
        if urlsplit(response.geturl()).scheme!='https':
            raise ValueError('HTTPS가 아닌 다운로드 리디렉션을 거부했습니다.')
        while block:=response.read(1024*1024):
            output.write(block)


def _curl_executable():
    if os.name!='nt':return None
    path=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/curl.exe'
    return str(path) if path.is_file() else None


def download(url,path,emit=print):
    if urlsplit(url).scheme!='https':raise ValueError('모델 주소는 HTTPS여야 합니다.')
    last=None
    for attempt in range(1,3):
        try:
            _python_download(url,path);return
        except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
            last=exc
            emit(f'연결 시도 {attempt}/2 실패: {type(exc).__name__}: {safe_error(exc)}')
            emit(guidance(exc))
            if attempt==1:time.sleep(1)
    curl=_curl_executable()
    if curl:
        emit('Windows 기본 다운로드 도구로 재시도합니다. HTTPS 인증서 검증은 유지합니다.')
        result=subprocess.run([curl,'--silent','--show-error','--fail','--location',
            '--proto','=https','--proto-redir','=https','--connect-timeout','20','--max-time','180',
            '--retry','1','--retry-delay','2','--output',str(path),url],capture_output=True)
        if result.returncode==0:return
        detail=result.stderr.decode('utf-8',errors='replace')
        raise RuntimeError(f'Windows 다운로드도 실패했습니다 (curl {result.returncode}): {safe_error(detail)}') from last
    raise last


def ensure_model(cache,model,emit=print):
    target=cache/model.relative_path
    if target.is_file() and digest(target)==model.sha256:
        emit(f'{model.name}: 기존 파일 검증 완료 · 재사용');return
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=[]
    try:
        with NamedTemporaryFile(dir=target.parent,delete=False) as f:
            archive=Path(f.name);temporary.append(archive)
        emit(f'{model.name}: 공식 서버 {urlsplit(model.url).hostname}에서 받습니다.')
        download(model.url,archive,emit)
        prepared=archive
        if model.member:
            with NamedTemporaryFile(dir=target.parent,delete=False) as f:
                prepared=Path(f.name);temporary.append(prepared)
                with ZipFile(archive) as z, z.open(model.member) as member:
                    while block:=member.read(1024*1024):f.write(block)
        if digest(prepared)!=model.sha256:
            raise ValueError(f'{model.name}: SHA-256 검증 실패. 다운로드 파일을 사용하지 않습니다.')
        prepared.replace(target)
        emit(f'{model.name}: 다운로드·SHA-256 검증 완료')
    finally:
        for path in temporary:path.unlink(missing_ok=True)


def prepare_all(cache,emit=print):
    for model in (*MODELS, *NEURAL_MODELS):ensure_model(cache,model,emit)
