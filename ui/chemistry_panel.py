"""고1 통합과학 수준의 성분별 화학 정보 안내. 기존 DB와 독립적이다."""
import re
import streamlit as st

# 단일 분자식이 명확한 성분만 수록한다. 혼합물/고분자는 추정하지 않는다.
# 표기는 기존 성분명과 공백·대소문자 차이만 허용한다.
CHEMISTRY = {
    '글리세린': ('C3H8O3', '뚜렷한 산·염기성 없음', '일반적인 수용액 조건에서 뚜렷한 산·염기성으로 분류하지 않는 보습 성분'),
    '글리세롤': ('C3H8O3', '뚜렷한 산·염기성 없음', '일반적인 수용액 조건에서 뚜렷한 산·염기성으로 분류하지 않는 보습 성분'),
    '시트릭애씨드': ('C6H8O7', '산', 'pH 조절에 사용될 수 있음'),
    '구연산': ('C6H8O7', '산', 'pH 조절에 사용될 수 있음'),
    '락틱애씨드': ('C3H6O3', '산', 'pH 조절 등에 사용될 수 있음'),
    '젖산': ('C3H6O3', '산', 'pH 조절 등에 사용될 수 있음'),
    '소듐하이드록사이드': ('NaOH', '염기', 'pH 조절에 사용될 수 있음'),
    '수산화나트륨': ('NaOH', '염기', 'pH 조절에 사용될 수 있음'),
    '포타슘하이드록사이드': ('KOH', '염기', 'pH 조절에 사용될 수 있음'),
    '수산화칼륨': ('KOH', '염기', 'pH 조절에 사용될 수 있음'),
    '정제수': ('H2O', '중성', '순수한 물은 25°C에서 pH 7인 중성 물질'),
    '물': ('H2O', '중성', '순수한 물은 25°C에서 pH 7인 중성 물질'),
    '아쿠아': ('H2O', '중성', '순수한 물은 25°C에서 pH 7인 중성 물질'),
    '워터': ('H2O', '중성', '순수한 물은 25°C에서 pH 7인 중성 물질'),
    '에탄올': ('C2H6O', None, '용매'),
    '에틸알코올': ('C2H6O', None, '용매'),
    '나이아신아마이드': ('C6H6N2O', None, '피부 관리 성분'),
    '우레아': ('CH4N2O', None, '보습 성분'),
    '프로판다이올': ('C3H8O2', None, '보습·용매'),
    '프로필렌글라이콜': ('C3H8O2', None, '보습·용매'),
    '부틸렌글라이콜': ('C4H10O2', None, '보습·용매'),
    '1,2-헥산다이올': ('C6H14O2', None, '보습·용매'),
    '펜틸렌글라이콜': ('C5H12O2', None, '보습·용매'),
    '에틸헥실글리세린': ('C11H24O3', None, '피부 컨디셔닝'),
    '판테놀': ('C9H19NO4', None, '보습'),
    '알란토인': ('C4H6N4O3', None, '피부 컨디셔닝'),
    '카페인': ('C8H10N4O2', None, '피부 컨디셔닝'),
    '토코페롤': ('C29H50O2', None, '산화 방지'),
    '아스코빅애씨드': ('C6H8O6', '산', '비타민 C 성분'),
    '벤조익애씨드': ('C7H6O2', '산', '보존 관련 성분'),
    '소르빅애씨드': ('C6H8O2', '산', '보존 관련 성분'),
    '살리실릭애씨드': ('C7H6O3', '산', '피부 관리 성분'),
    '글라이콜릭애씨드': ('C2H4O3', '산', '피부 관리 성분'),
    '말릭애씨드': ('C4H6O5', '산', 'pH 조절'),
    '타타릭애씨드': ('C4H6O6', '산', 'pH 조절'),
    '소듐바이카보네이트': ('NaHCO3', '약염기성', '수용액에서 약염기성'),
    '탄산수소나트륨': ('NaHCO3', '약염기성', '수용액에서 약염기성'),
    '소듐카보네이트': ('Na2CO3', '염기', '수용액에서 염기성'),
    '트라이에탄올아민': ('C6H15NO3', '염기', 'pH 조절'),
    '아르지닌': ('C6H14N4O2', None, '아미노산; 용액의 산·염기성은 조건에 따라 달라짐'),
    '글라이신': ('C2H5NO2', None, '아미노산'),
    '소듐클로라이드': ('NaCl', None, '점도 조절'),
    '징크옥사이드': ('ZnO', None, '피부 보호·자외선 차단 원료'),
    '티타늄디옥사이드': ('TiO2', None, '색소·자외선 차단 원료'),
    '소듐벤조에이트': ('C7H5NaO2', None, '보존제'),
    '포타슘솔베이트': ('C6H7KO2', None, '보존제'),
    '벤질알코올': ('C7H8O', None, '용매·향료 성분'),
    '페녹시에탄올': ('C8H10O2', None, '보존제'),
    '다이소듐이디티에이': ('C10H14N2Na2O8', None, '금속이온 봉쇄'),
    '나이아신아마이드': ('C6H6N2O', None, '피부 관리'),

    '아젤라익애씨드': ('C9H16O4', '산', '약산 성질을 가진 유기산'),
    '아젤라산': ('C9H16O4', '산', '약산 성질을 가진 유기산'),
    '만델릭애씨드': ('C8H8O3', '산', '약산 성질을 가진 유기산'),
    '만델산': ('C8H8O3', '산', '약산 성질을 가진 유기산'),
    '석시닉애씨드': ('C4H6O4', '산', '약산 성질을 가진 유기산'),
    '호박산': ('C4H6O4', '산', '약산 성질을 가진 유기산'),
    '푸마릭애씨드': ('C4H4O4', '산', '약산 성질을 가진 유기산'),
    '퓨마릭애씨드': ('C4H4O4', '산', '약산 성질을 가진 유기산'),
    '아세틱애씨드': ('C2H4O2', '산', '물에 녹으면 약산의 성질을 나타내는 유기산'),
    '아세트산': ('C2H4O2', '산', '물에 녹으면 약산의 성질을 나타내는 유기산'),
    '포스포릭애씨드': ('H3PO4', '산', '산의 성질을 가지며 pH 조절에 사용될 수 있음'),
    '인산': ('H3PO4', '산', '산의 성질을 가지며 pH 조절에 사용될 수 있음'),
    '하이드로클로릭애씨드': ('HCl', '산', '수용액에서 강산의 성질을 나타냄'),
    '염산': ('HCl', '산', '수용액에서 강산의 성질을 나타냄'),
    '암모니아': ('NH3', '염기', '물에 녹아 염기성 용액을 형성할 수 있음'),
    '암모늄하이드록사이드': ('NH4OH', '염기', '암모니아 수용액을 나타내는 관용 표기이며 염기성을 띨 수 있음'),
    '소듐시트레이트': ('C6H5Na3O7', '조건에 따라 약염기성', '시트르산의 염으로 수용액의 산·염기성은 조성과 농도에 따라 달라짐'),
    '트라이소듐시트레이트': ('C6H5Na3O7', '조건에 따라 약염기성', '시트르산의 염으로 수용액의 산·염기성은 조성과 농도에 따라 달라짐'),
    '소듐락테이트': ('C3H5NaO3', '조건에 따라 약염기성', '젖산의 염으로 수용액에서 약염기성 성질을 보일 수 있음'),
    '소듐아스코베이트': ('C6H7NaO6', '조건에 따라 약염기성', '아스코르브산의 염으로 수용액의 성질은 조건에 따라 달라짐'),
    '소듐하이알루로네이트': (None, None, '고분자이므로 단일 분자식과 산·염기성을 단정하지 않음'),
}
ELEMENTS = {'C': '탄소', 'H': '수소', 'O': '산소', 'N': '질소', 'Na': '나트륨', 'K': '칼륨', 'Zn': '아연', 'Ti': '타이타늄', 'Cl': '염소', 'P': '인'}


def _key(name: str) -> str:
    return re.sub(r'\s+', '', name).casefold()


_LOOKUP = {_key(name): info for name, info in CHEMISTRY.items()}


def chemical_info(name: str):
    """검증 대상 성분의 화학식/산·염기 성질만 조회. 미등록은 None."""
    return _LOOKUP.get(_key(name))


def element_counts(formula: str) -> dict[str, int]:
    """현재 수록한 괄호 없는 단순 화학식만 처리한다."""
    pieces = re.findall(r'([A-Z][a-z]?)(\d*)', formula)
    if not pieces or ''.join(a + b for a, b in pieces) != formula:
        raise ValueError('지원하지 않는 화학식')
    counts = {}
    for symbol, count in pieces:
        counts[symbol] = counts.get(symbol, 0) + int(count or '1')
    return counts


def render_chemistry_panel(result) -> None:
    """기존 AnalysisResult의 성분명만 읽고 DB·분석 결과는 변경하지 않는다."""
    names = list(dict.fromkeys(row.canonical_name for row in result.rows if row.canonical_name))
    known = [name for name in names if chemical_info(name) and chemical_info(name)[0]]
    st.subheader('🌱 화학 성분 분석')
    st.caption('통합과학에서 배우는 화학식·구성 원소·산과 염기의 성질을 살펴봅니다. 단일 화학식이 명확한 일부 성분만 제공해요.')
    if not known:
        st.info('현재 분석 목록에서 화학 정보가 준비된 성분이 없습니다. 정보가 없다는 뜻이지 안전하거나 중성이라는 뜻은 아닙니다.')
        return
    selected = st.selectbox('화학 정보를 확인할 성분', known, key='chemistry_selected_ingredient')
    formula, acid_base, role = chemical_info(selected)
    first, second = st.tabs(['구성 원소', '산·염기 특성'])
    with first:
        st.markdown(f'**{selected}** · 화학식: **{formula}**')
        st.dataframe([{'원소 기호': symbol, '원소 이름': ELEMENTS.get(symbol, symbol), '원자 개수': number}
                      for symbol, number in element_counts(formula).items()], hide_index=True, width='stretch')
        st.caption('화학식에 나타난 분자 1개(또는 화학식 단위 1개)의 원자 개수입니다. 제품 속 함량은 알 수 없습니다.')
    with second:
        if acid_base:
            st.markdown(f'**{selected}: {acid_base}**')
            st.write(role.rstrip('.') + '.')
            if acid_base == '중성':
                st.caption('순수한 물의 중성은 25°C 기준입니다. 화장품 완제품의 pH가 중성이라는 뜻은 아닙니다.')
        else:
            st.info('이 성분은 확인된 자료만으로 산·염기성을 단정하기 어렵습니다. 미분류가 중성이라는 뜻은 아닙니다.')
            st.write(role)
        st.caption('개별 원료의 성질만 설명합니다. 전성분표만으로 완제품의 pH나 실제 반응 여부를 판단할 수 없습니다.')
    unknown_count = len(names) - len(known)
    if unknown_count:
        st.caption(f'화학 정보 미제공 성분: {unknown_count}개 (추정하지 않고 제외)')
    st.caption('참고 자료: PubChem (pubchem.ncbi.nlm.nih.gov). 성분별 정보는 교육용이며 실제 배합 특성을 뜻하지 않습니다.')
