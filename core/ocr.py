"""한국어·영어 CPU OCR. 모델 자원만 공유하고 사용자 인식 결과는 공유하지 않는다."""
from pathlib import Path
from statistics import median
from threading import RLock
import math

import numpy as np
from PIL import Image

from core.database import ROOT
from core.models import OCRBlock, OCRLine, OCRResult, OCRToken
from core.normalize import normalize_key, normalize_text

MODEL_ROOT = ROOT / ".cache/easyocr"


def _bounds(block: OCRBlock) -> tuple[float, float, float, float]:
    xs, ys = zip(*block.bbox)
    return min(xs), min(ys), max(xs), max(ys)


def _overlap(a: OCRBlock, b: OCRBlock) -> float:
    ax, ay, ar, ab = _bounds(a)
    bx, by, br, bb = _bounds(b)
    intersection = max(0, min(ar, br) - max(ax, bx)) * max(0, min(ab, bb) - max(ay, by))
    union = (ar - ax) * (ab - ay) + (br - bx) * (bb - by) - intersection
    return intersection / union if union else 0


def _row_lines(blocks: list[OCRBlock]) -> list[OCRLine]:
    rows: list[list[OCRBlock]] = []
    for block in sorted(blocks, key=lambda b: (_bounds(b)[1], _bounds(b)[0])):
        _, top, _, bottom = _bounds(block)
        center = (top + bottom) / 2
        matching = []
        for index, row in enumerate(rows):
            row_top = median(_bounds(b)[1] for b in row)
            row_bottom = median(_bounds(b)[3] for b in row)
            distance = abs(center - (row_top + row_bottom) / 2)
            if distance <= 0.5 * min(bottom - top, row_bottom - row_top):
                matching.append((distance, index))
        if matching:
            rows[min(matching)[1]].append(block)
        else:
            rows.append([block])
    lines = []
    for row in sorted(rows, key=lambda r: median(_bounds(b)[1] for b in r)):
        row.sort(key=lambda b: _bounds(b)[0])
        lines.append(OCRLine(" ".join(b.raw_text for b in row), tuple(b.source_index for b in row)))
    return lines


def arrange_blocks(blocks: tuple[OCRBlock, ...], reading_order: str) -> tuple[tuple[OCRLine, ...], tuple[int, ...]]:
    """같은 위치의 중복만 제외한 뒤 줄 또는 열 순서로 조립한다."""
    if reading_order not in {"rows", "columns"}:
        raise ValueError("읽기 순서는 rows 또는 columns여야 합니다.")
    retained = []
    suppressed = []
    for block in sorted(blocks, key=lambda b: (-b.confidence, b.source_index)):
        if any(normalize_key(b.raw_text) == normalize_key(block.raw_text) and _overlap(b, block) >= 0.8 for b in retained):
            suppressed.append(block.source_index)
        else:
            retained.append(block)
    if reading_order == "rows" or not retained:
        return tuple(_row_lines(retained)), tuple(sorted(suppressed))
    # 큰 수직 여백으로 분리 가능한 열만 왼쪽부터 읽는다. 구분선이 없는
    # 복잡한 배치의 의미까지 추측하지 않으며 최종 읽기 순서는 사용자가 확인한다.
    gap_limit = 2 * median(_bounds(b)[3] - _bounds(b)[1] for b in retained)
    columns: list[list[OCRBlock]] = []
    right_edge = -math.inf
    for block in sorted(retained, key=lambda b: _bounds(b)[0]):
        left, _, right, _ = _bounds(block)
        if not columns or left - right_edge > gap_limit:
            columns.append([])
        columns[-1].append(block)
        right_edge = max(right_edge, right)
    return tuple(line for column in columns for line in _row_lines(column)), tuple(sorted(suppressed))


def parse_output(output, reading_order: str = "rows") -> OCRResult:
    blocks = []
    for index, (bbox, text, confidence) in enumerate(output):
        if not isinstance(text, str):
            raise ValueError("OCR 텍스트가 문자열이 아닙니다.")
        points = tuple(tuple(float(c) for c in point) for point in bbox)
        score = float(confidence)
        if len(points) != 4 or any(len(point) != 2 or not all(math.isfinite(c) for c in point) for point in points):
            raise ValueError("OCR 위치 좌표 형식이 올바르지 않습니다.")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("OCR 점수 형식이 올바르지 않습니다.")
        if text.strip():
            block = OCRBlock(text, points, score, index)
            x, y, right, bottom = _bounds(block)
            if right <= x or bottom <= y:
                raise ValueError("OCR 영역의 크기가 올바르지 않습니다.")
            blocks.append(block)
    lines, suppressed = arrange_blocks(tuple(blocks), reading_order)
    raw_text = "\n".join(line.raw_text for line in lines)
    return OCRResult("ok" if lines else "empty", raw_text, tuple(blocks), lines, suppressed, reading_order=reading_order)


def tokens_from_ocr(result: OCRResult) -> tuple[OCRToken, ...]:
    # 위치 연결은 문자 단위 추정이 아니라 원래 OCR 줄의 영역들이다.
    return tuple(OCRToken(token, line.source_indices) for line in result.lines for token in normalize_text(line.raw_text))


class OCREngine:
    def __init__(self, model_root: Path = MODEL_ROOT, reader_factory=None):
        self.model_root = model_root
        self._reader_factory = reader_factory
        self._reader = None
        self._lstm = None
        self._neural = None
        self.neural_enabled = reader_factory is None
        self._lock = RLock()

    def prepare(self) -> OCRResult:
        """최초 한 번 공식 모델을 다운로드·검증한다. 실패한 객체는 캐시하지 않는다."""
        with self._lock:
            if self._reader is not None:
                return OCRResult("ready")
            try:
                factory = self._reader_factory
                if factory is None:
                    import torch
                    import easyocr
                    torch.set_num_threads(2)
                    factory = easyocr.Reader
            except ImportError:
                return OCRResult("dependency_error", message="OCR 도구가 설치되지 않았습니다. requirements.txt로 의존성을 설치해 주세요.")
            except Exception:
                return OCRResult("dependency_error", message="OCR 도구를 불러올 수 없습니다. PyTorch·torchvision 설치 조합을 확인해 주세요.")
            try:
                self._reader = factory(
                    ["ko", "en"], gpu=False, verbose=False, download_enabled=True,
                    model_storage_directory=str(self.model_root / "model"),
                    user_network_directory=str(self.model_root / "user_network"),
                )
            except Exception as exc:
                return OCRResult("model_error", message=f"OCR 모델 설치·검증에 실패했습니다 ({type(exc).__name__}). 저장 공간·모델 폴더 권한·GitHub 다운로드 연결을 확인한 뒤 다시 시도해 주세요.")
        return OCRResult("ready")

    def recognize(self, image: Image.Image, reading_order: str = "rows", *, accurate: bool = False) -> OCRResult:
        if reading_order not in {"rows", "columns"}:
            return OCRResult("execution_error", message="읽기 순서를 다시 선택해 주세요.")
        with self._lock:
            if accurate:
                if self._lstm is None:
                    from core.lstm_ocr import LSTMReader
                    self._lstm = LSTMReader()
                return self._lstm.recognize(image)
            prepared = self.prepare()
            if prepared.status != "ready":
                return prepared
            try:
                output = self._reader.readtext(
                    np.array(image.convert("RGB")), detail=1, paragraph=False,
                    batch_size=1, workers=0, canvas_size=2560,
                    # EasyOCR 1.7.2의 긴 줄 beamsearch는 수치 overflow·잘림이 관찰됐다.
                    # 영역 탐색에는 기존 greedy를, 정밀 재인식에는 별도 LSTM 인식기를 사용한다.
                    decoder="greedy",
                    width_ths=0.5, text_threshold=0.7, low_text=0.4,
                    contrast_ths=0.1, adjust_contrast=0.5,
                )
                return parse_output(output, reading_order)
            except Exception:
                return OCRResult("execution_error", message="사진의 글자를 인식하는 중 오류가 발생했습니다. 사진 크기·회전·영역을 조정해 다시 시도하거나 직접 입력해 주세요.", reading_order=reading_order)

    def recognize_line(self, image: Image.Image) -> OCRResult:
        """선택한 실제 글자 줄/단어를 단일 행 모드로 읽는다. 원문·좌표는 그대로 반환."""
        with self._lock:
            if self._lstm is None:
                from core.lstm_ocr import LSTMReader
                self._lstm = LSTMReader()
            return self._lstm.recognize_line(image)

    def recognize_neural(self, image, *, limit=1600, dewarp=False):
        with self._lock:
            if self._neural is None:
                self._neural = NeuralReader()
            return self._neural.recognize(image, limit=limit, dewarp=dewarp)

    def prepare_neural(self):
        with self._lock:
            if self._neural is None:
                self._neural = NeuralReader()
            return self._neural.prepare()

    def prepare_accurate(self) -> OCRResult:
        with self._lock:
            if self._lstm is None:
                from core.lstm_ocr import LSTMReader
                self._lstm = LSTMReader()
            return self._lstm.prepare()


class NeuralReader:
    """공식 PP-OCRv5 검출·한국어 인식 ONNX. 사진은 로컬 CPU 메모리에서만 처리."""
    REVISION = "ppocr-v5-korean-1"

    def __init__(self, model_root=None):
        self.model_root = Path(model_root or ROOT / ".cache/ppocr_v5")
        self.detector = self.recognizer = None
        self.characters = ()
        self._lock = RLock()

    def prepare(self):
        with self._lock:
            if self.detector is not None and self.recognizer is not None:
                return OCRResult("ready")
            try:
                import onnxruntime as ort
                import yaml
            except ImportError:
                return OCRResult("dependency_error", message="새 한국어 OCR 도구를 설치하려면 setup_windows.bat을 한 번 실행해 주세요.")
            try:
                from scripts.ocr_downloads import NEURAL_MODELS, ensure_model
                for model in NEURAL_MODELS:
                    ensure_model(self.model_root.parent, model, emit=lambda _: None)
                config = yaml.safe_load((self.model_root / "korean.yml").read_text(encoding="utf-8"))
                self.characters = ("", *config["PostProcess"]["character_dict"], " ")
                options = ort.SessionOptions()
                options.intra_op_num_threads = 2
                options.inter_op_num_threads = 1
                options.log_severity_level = 3
                options.enable_mem_pattern = False
                self.detector = ort.InferenceSession(str(self.model_root / "det.onnx"), options, providers=["CPUExecutionProvider"])
                self.recognizer = ort.InferenceSession(str(self.model_root / "korean.onnx"), options, providers=["CPUExecutionProvider"])
            except Exception as exc:
                self.detector = self.recognizer = None
                return OCRResult("model_error", message=f"새 한국어 OCR 모델 준비 실패 ({type(exc).__name__}). retry_ocr_windows.bat으로 연결·파일 검사를 다시 실행해 주세요.")
            return OCRResult("ready")

    def read_line(self, bgr):
        import cv2
        import unicodedata
        h, w = bgr.shape[:2]
        width = max(8, math.ceil(w * 48 / h))
        # 지나치게 긴 줄의 메모리를 제한한다. 정상 라벨의 한 줄을 잘라내지는 않는다.
        if width > 12000:
            raise ValueError("한 줄의 글자가 너무 많습니다.")
        array = cv2.resize(bgr, (width, 48)).astype(np.float32) / 127.5 - 1
        scores = self.recognizer.run(None, {self.recognizer.get_inputs()[0].name: array.transpose(2, 0, 1)[None]})[0][0]
        if scores.shape[-1] != len(self.characters):
            raise ValueError("모델과 문자 사전의 버전이 다릅니다.")
        previous = -1
        text, confidence = [], []
        for index, score in zip(scores.argmax(1), scores.max(1)):
            if index and index != previous:
                text.append(self.characters[index])
                confidence.append(float(score))
            previous = index
        return unicodedata.normalize("NFC", "".join(text)), sum(confidence) / max(1, len(confidence))

    def detect(self, bgr, limit):
        import cv2
        h, w = bgr.shape[:2]
        scale = min(1, limit / max(h, w))
        nh, nw = max(32, round(h * scale / 32) * 32), max(32, round(w * scale / 32) * 32)
        array = cv2.resize(bgr, (nw, nh)).astype(np.float32) / 255
        array = (array - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
        probabilities = self.detector.run(None, {self.detector.get_inputs()[0].name: array.transpose(2, 0, 1)[None]})[0][0, 0]
        contours, _ = cv2.findContours((probabilities > .3).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:1000]:
            area = cv2.contourArea(contour)
            if area < 12:
                continue
            mask = np.zeros(probabilities.shape, np.uint8)
            cv2.drawContours(mask, [contour], -1, 1, -1)
            if cv2.mean(probabilities, mask=mask)[0] < .55:
                continue
            (cx, cy), (rw, rh), angle = cv2.minAreaRect(contour)
            if min(rw, rh) < 3:
                continue
            pad = area * 1.5 / max(1, cv2.arcLength(contour, True))
            box = cv2.boxPoints(((cx, cy), (rw + 2 * pad, rh + 2 * pad), angle))
            box[:, 0] *= w / nw
            box[:, 1] *= h / nh
            pairs = box[np.argsort(box[:, 0])]
            left = pairs[:2][np.argsort(pairs[:2, 1])]
            right = pairs[2:][np.argsort(pairs[2:, 1])]
            box = np.array([left[0], right[0], right[1], left[1]], np.float32)
            contour = contour.astype(np.float32)
            contour[:, :, 0] *= w / nw
            contour[:, :, 1] *= h / nh
            boxes.append((box, contour))
        return boxes

    @staticmethod
    def crop_line(bgr, box, contour, dewarp=False):
        import cv2
        width = max(4, round(max(np.linalg.norm(box[0] - box[1]), np.linalg.norm(box[2] - box[3]))))
        height = max(4, round(max(np.linalg.norm(box[0] - box[3]), np.linalg.norm(box[1] - box[2]))))
        if width * height > 20_000_000:
            raise ValueError("글자 영역이 너무 큽니다.")
        target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
        matrix = cv2.getPerspectiveTransform(box, target)
        cropped = cv2.warpPerspective(bgr, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE)
        if not dewarp or width < height * 3:
            return cropped
        # 원근·기울기를 먼저 제거한 좌표에서 검출 마스크의 위·아래 윤곽을 추적한다.
        local = cv2.perspectiveTransform(contour, matrix).astype(np.int32)
        mask = np.zeros((height, width), np.uint8)
        cv2.drawContours(mask, [local], -1, 1, -1)
        columns = np.flatnonzero(mask.sum(axis=0) > 0)
        if len(columns) < 8:
            return cropped
        top = mask.argmax(axis=0).astype(np.float32)
        bottom = height - 1 - mask[::-1].argmax(axis=0)
        center = (top + bottom) / 2
        center = np.interp(np.arange(width), columns, center[columns]).astype(np.float32)
        center = cv2.GaussianBlur(center[None], (0, 1), sigmaX=max(1, width / 100))[0]
        half = max(5, float(np.median((bottom - top)[columns])) * 1.1)
        # 수평 길이는 보존하고 휜 줄의 중심만 편다. 잘린 획을 만들어내지는 않는다.
        height_out = max(10, round(half * 2))
        mx = np.broadcast_to(np.arange(width, dtype=np.float32)[None], (height_out, width)).copy()
        my = center[None] + np.linspace(-half, half, height_out, dtype=np.float32)[:, None]
        return cv2.remap(cropped, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def recognize(self, image, *, limit=1600, dewarp=False):
        import cv2
        with self._lock:
            prepared = self.prepare()
            if prepared.status != "ready":
                return prepared
            try:
                bgr = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
                output = []
                for box, contour in self.detect(bgr, limit):
                    text, confidence = self.read_line(self.crop_line(bgr, box, contour, dewarp))
                    if text.strip() and confidence >= .3:
                        output.append((box.tolist(), text, min(1., confidence)))
                return parse_output(output)
            except Exception as exc:
                return OCRResult("execution_error", message=f"한국어 줄 인식 실패 ({type(exc).__name__}). 다시 촬영하거나 직접 입력해 주세요.")
