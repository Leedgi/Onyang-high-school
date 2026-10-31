"""동일한 확정 결과 → 유래별 목록 → 한글 글꼴을 포함한 PDF. 사진·원문 자동 첨부 없음."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import math
from pathlib import Path
from threading import RLock
from xml.sax.saxutils import escape

from core.models import AnalysisResult, ORIGINS, DETAIL_ORIGINS, DETAIL_ORIGIN_COLORS
from ui.review_notes import review_notes

COLORS = {"석유계": "#356351", "식물성": "#7f9d68", "기타": "#b5c7a2", "확인 필요": "#e5e7df", **DETAIL_ORIGIN_COLORS}
FONT_PATH = Path(__file__).with_name("assets") / "fonts/NanumGothic-Regular.ttf"
_FONT_LOCK = RLock()


def visible_ratio(result):
    return result.detail_count_ratio or result.count_ratio


def origin_label(row):
    category=row.detail_origin or row.origin
    return category + (" (추정)" if row.detail_is_estimate and category!="확인 필요" else "")


def ingredient_groups(result: AnalysisResult):
    """분류를 다시 계산하지 않고 같은 B 결과의7분류 또는 v1 유래로 묶는다."""
    detailed=result.detail_count_ratio is not None
    categories=DETAIL_ORIGINS if detailed else ORIGINS
    return tuple((origin,tuple(row for row in result.rows
                               if ((row.detail_origin or "확인 필요") if detailed else row.origin)==origin)) for origin in categories)


def build_pdf(result: AnalysisResult) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    with _FONT_LOCK:
        if "IngredientKorean" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("IngredientKorean", str(FONT_PATH)))
    normal = ParagraphStyle("body", fontName="IngredientKorean", fontSize=9, leading=15,
                            wordWrap="CJK", textColor=colors.HexColor("#28382e"), spaceAfter=6)
    heading = ParagraphStyle("heading", parent=normal, fontSize=13, leading=20, spaceBefore=12, spaceAfter=8, keepWithNext=True)
    title = ParagraphStyle("title", parent=normal, fontSize=21, leading=29, spaceAfter=14)
    small = ParagraphStyle("small", parent=normal, fontSize=8, leading=12)

    def p(text, style=normal):
        # Plain user names cannot become PDF markup or remote image requests.
        clean = ''.join(c for c in str(text) if c in '\n\t' or ord(c) >= 32)
        return Paragraph(escape(clean).replace('\n', '<br/>'), style)

    class Donut(Flowable):
        def __init__(self):
            super().__init__()
            self.width = 210
            self.height = 210

        def draw(self):
            c = self.canv
            cx, cy, radius, hole = 105, 105, 88, 48
            angle = 90.0
            ratio = visible_ratio(result)
            if ratio and ratio.denominator:
                for origin, value in ratio.values.items():
                    if value <= 0:
                        continue
                    span = value * 3.6
                    c.setFillColor(colors.HexColor(COLORS[origin]))
                    c.wedge(cx-radius, cy-radius, cx+radius, cy+radius, angle, -span, stroke=0, fill=1)
                    middle = math.radians(angle-span/2)
                    c.setFillColor(colors.white if origin == "석유계" else colors.HexColor("#183f31"))
                    c.setFont("IngredientKorean", 9)
                    c.drawCentredString(cx+68*math.cos(middle), cy+68*math.sin(middle)-3, f"{value:.1f}%")
                    angle -= span
            else:
                c.setFillColor(colors.HexColor("#e5e7df"))
                c.circle(cx, cy, radius, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.circle(cx, cy, hole, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#183f31"))
            c.setFont("IngredientKorean", 12)
            c.drawCentredString(cx, cy-4, f"{int(ratio.denominator) if ratio else 0}개 성분")

    data = BytesIO()
    doc = SimpleDocTemplate(data, pagesize=A4, rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=42,
                            title="친환경 제품 성분 정보 분석", author="성분 정보 분석")
    content = [p("친환경 제품 성분 정보 분석", title),
               p(datetime.now(timezone(timedelta(hours=9))).strftime("작성일: %Y-%m-%d %H:%M (한국 시간)"), small),
               p("분석에 포함한 성분 목록의 리포트입니다. 제품의 친환경성·안전성을 인증하지 않습니다.")]
    if result.automatic:
        excluded = sum(not d.selected_name for d in result.automatic_decisions)
        content.append(p(f"자동 분석: 미식별 {excluded}개 제외. 비율은 분석에 포함한 성분만 기준이며 전체 성분표의 비율이 아닐 수 있습니다."))
        content.append(p("이름 자동 선택·제외 내역", heading))
        for decision in result.automatic_decisions:
            content.append(p(f"{decision.draft.raw_text} → {decision.selected_name or '제외'} · {decision.reason}", small))
    ratio = visible_ratio(result)
    if ratio:
        legend = [[p("원료 유래"), p("성분명 개수 비율")]] + [[p(k), p(f"{v:.1f}%")] for k, v in ratio.values.items()]
        chart = Table([[Donut(), Table(legend, colWidths=[105, 145])]], colWidths=[225, 290])
        chart.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        content += [chart, p(f"{ratio.label} · 중복 제외 {int(ratio.denominator)}개. 확인 필요도 분모에 포함합니다. 배합 함량이 아닙니다.")]
    else:
        content.append(p("분석할 성분이 없습니다."))
    if result.detail_count_ratio:
        content.append(p("7분류에는 이름 규칙 기반 추정이 포함됩니다. (추정) 표시는 개별 제조사 원료 확인이 아니며, 합성은 석유계와 같은 뜻이 아닙니다. 제품의 비건·안전·친환경성을 판정하지 않습니다."))
    content.append(p("유래별 성분 목록", heading))
    for origin, rows in ingredient_groups(result):
        content.append(p(f"{origin} · {len(rows)}개", heading))
        if not rows:
            content.append(p("해당 성분 없음"))
            continue
        table = Table([[p("성분"), p("유래"), p("기능")]] + [
            [p(r.canonical_name), p(origin_label(r)), p(", ".join(r.functions) or "자료 없음")] for r in rows
        ], colWidths=[165, 100, 250], repeatRows=1, hAlign="LEFT", splitInRow=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7eddf")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#dedfd5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        content.extend([table, Spacer(1, 6)])
    content.append(p("산성도·인체·환경 확인 사항", heading))
    for label, description in review_notes(result):
        content.extend([p(label, heading), p(description)])
    content.append(p("등록된 성분별 주의 정보", heading))
    cautions = [record for records in result.cautions.values() for record in records]
    if not cautions:
        content.append(p("등록된 주의 자료가 없습니다. 안전하다는 뜻은 아닙니다."))
    for record in cautions:
        content += [p(record.name, heading), p(record.reason), p(record.restriction),
                    p(f"국가: {record.country} / 제품: {record.product_type}"),
                    p(f"사용 조건: {record.use_condition} / 농도 조건: {record.concentration_condition}"),
                    p(f"출처: {record.source_url}\n확인일: {record.checked_on}", small)]
    content += [p("성분별 근거와 출처", heading), p("일부 근거는 2019년 비공식 자료입니다. 최신 규제·안전성 검토를 대신하지 않습니다.")]
    for row in result.rows:
        content += [p(row.canonical_name, heading), p(row.reason),
                    p(f"확인 필요 원인: {row.uncertainty_reason or '해당 없음'}", small),
                    p(f"출처: {row.source_url or '자료 없음'}\n확인일: {row.checked_on or '자료 없음'}", small)]

        if row.detail_origin:
            content += [p(f"7분류: {origin_label(row)} / 검토 수준: {row.detail_confidence}", small),
                        p(row.detail_reason, small),p(f"7분류 자료 출처: {row.detail_source_url}", small)]

    def page_number(canvas, document):
        canvas.setFont("IngredientKorean", 8)
        canvas.setFillColor(colors.HexColor("#657268"))
        canvas.drawRightString(A4[0]-40, 24, f"{document.page}")

    doc.build(content, onFirstPage=page_number, onLaterPages=page_number)
    return data.getvalue()
