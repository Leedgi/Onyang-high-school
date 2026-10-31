"""인쇄된 한국어 라벨용 로컬 LSTM AI 인식기. Windows wheel에 실행 라이브러리가 포함된다."""
import hashlib
from dataclasses import replace
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
import urllib.request

from core.database import ROOT
from core.models import OCRResult, OCRLine

REVISION = "e12c65a915945e4c28e237a9b52bc4a8f39a0cec"
MODEL_HASHES = {
    "kor": "f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff",
    "eng": "8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba",
}


def prepare_models(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for language, expected in MODEL_HASHES.items():
        path = folder / f"{language}.traineddata"
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            continue
        url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/{REVISION}/{language}.traineddata"
        with urllib.request.urlopen(url, timeout=45) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("LSTM 모델 체크섬이 일치하지 않습니다. 사용하지 않습니다.")
        temporary = None
        try:
            with NamedTemporaryFile(dir=folder, delete=False) as file:
                temporary = Path(file.name)
                file.write(content)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class LSTMReader:
    def __init__(self, folder: Path = ROOT / ".cache/tessdata_best"):
        self.folder = folder
        self._module = None
        self._apis = {}
        self._lock = RLock()

    def _api(self, language):
        if language not in self._apis:
            self._apis[language] = self._module.PyTessBaseAPI(
                path=str(self.folder), lang=language, oem=self._module.OEM.LSTM_ONLY,
                psm=self._module.PSM.SINGLE_BLOCK,
            )
        return self._apis[language]

    def prepare(self) -> OCRResult:
        with self._lock:
            if self._apis:
                return OCRResult("ready")
            try:
                import tesserocr
                self._module = tesserocr
            except (ImportError, OSError):
                return OCRResult("dependency_error", message="새 인쇄 글자 AI 도구가 없습니다. setup_windows.bat을 다시 실행해 주세요.")
            try:
                prepare_models(self.folder)
                self._api("kor")
            except Exception as exc:
                self._apis.clear()
                return OCRResult("model_error", message=f"인쇄 글자 AI 모델 준비·검증에 실패했습니다 ({type(exc).__name__}). 인터넷 연결과 저장 공간을 확인하고 설치를 다시 실행해 주세요.")
            return OCRResult("ready")

    def _recognize(self, image, language, single_line=False):
        from core.ocr import parse_output
        api = self._api(language)
        try:
            api.SetPageSegMode(self._module.PSM.SINGLE_LINE if single_line else self._module.PSM.SINGLE_BLOCK)
            api.SetImage(image.convert("RGB"))
            api.SetSourceResolution(300)
            api.Recognize()
            iterator = api.GetIterator()
            output = []
            if iterator is not None:
                level = self._module.RIL.WORD if single_line else self._module.RIL.TEXTLINE
                while True:
                    text, box = iterator.GetUTF8Text(level), iterator.BoundingBox(level)
                    if text and text.strip() and box:
                        x, y, right, bottom = box
                        confidence = float(iterator.Confidence(level)) / 100
                        if not math.isfinite(confidence):
                            raise ValueError("인식 점수가 유한한 숫자가 아닙니다.")
                        confidence = max(0.0, min(1.0, confidence))
                        output.append(([(x, y), (right, y), (right, bottom), (x, bottom)], text.strip(), confidence))
                    if not iterator.Next(level):
                        break
            result = parse_output(output)
            if single_line and result.blocks:
                # 쉼표의 작은 상자가 별도 물리적 줄로 밀리지 않도록 native 단어 순서를 보존한다.
                line = OCRLine(" ".join(b.raw_text for b in result.blocks), tuple(b.source_index for b in result.blocks))
                result = replace(result, raw_text=line.raw_text, lines=(line,), suppressed_indices=())
            return result
        finally:
            # 공유 자원에 마지막 사용자의 사진·인식 결과를 남기지 않는다.
            api.Clear()

    def recognize(self, image) -> OCRResult:
        return self._recognize_checked(image)

    def recognize_line(self, image) -> OCRResult:
        return self._recognize_checked(image, single_line=True)

    def _recognize_checked(self, image, single_line=False) -> OCRResult:
        with self._lock:
            ready = self.prepare()
            if ready.status != "ready":
                return ready
            try:
                korean = self._recognize(image, "kor", single_line)
                text = korean.raw_text
                hangul = sum("가" <= char <= "힣" for char in text)
                letters = sum(char.isalpha() for char in text)
                if not text or hangul / max(1, letters) < 0.15:
                    english = self._recognize(image, "eng", single_line)
                    if english.status == "ok":
                        return english
                return korean
            except Exception:
                return OCRResult("execution_error", message="인쇄 글자 AI 재인식에 실패했습니다. 사진을 다시 선택하거나 이름을 직접 입력해 주세요.")
