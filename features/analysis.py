"""학생 B의 공개 진입점. 화면과 OCR을 import하지 않는다."""
from core.analysis import analyze
from core.database import load_cautions, load_ingredients
from shared.contracts import AnalysisRequest, AnalysisResult


def analyze_confirmed(request: AnalysisRequest) -> AnalysisResult:
    """확정 목록→DB·유래·비율·주의. 잘못된 함량은 ValueError, 빈 목록은 no_data."""
    return analyze(list(request.ingredients), load_ingredients(), load_cautions(), request.mode,
                   automatic=request.automatic, automatic_decisions=request.automatic_decisions)
