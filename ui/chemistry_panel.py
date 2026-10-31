"""고1 통합과학 수준의 성분별 화학 정보 안내. 기존 DB와 독립적이다."""
import re
import streamlit as st

# 단일 분자식이 명확한 성분만 수록한다. 혼합물/고분자는 추정하지 않는다.
# 표기는 기존 성분명과 공백·대소문자 차이만 허용한다.
CHEMISTRY = {
    '글리세린': ('C3H8O3', None, '보습 성분'),
    '글리세롤': ('C3H8O3', None, '보습 성분'),
    '시트릭애씨드': ('C6H8O7', '산', 'pH 조절에 사용될 수 있음'),
    '구연산': ('C6H8O7', '산', 'pH 조절에 사용될 수 있음'),
    '락틱애씨드': ('C3H6O3', '산', 'pH 조절 등에 사용될 수 있음'),
    '젖산': ('C3H6O3', '산', 'pH 조절 등에 사용될 수 있음'),
    '소듐하이드록사이드': ('NaOH', '염기', 'pH 조절에 사용될 수 있음'),
    '수산화나트륨': ('NaOH', '염기', 'pH 조절에 사용될 수 있음'),
    '포타슘하이드록사이드': ('KOH', '염기', 'pH 조절에 사용될 수 있음'),
    '수산화칼륨': ('KOH', '염기', 'pH 조절에 사용될 수 있음'),
    '정제수': ('H2O', None, '용매'),
    '워터': ('H2O', None, '용매'),
    '에탄올': ('C2H6O', None, '용매'),
    '에틸알코올': ('C2H6O', None, '용매'),
    '나이아신아마이드': ('C6H6N2O', None, '피부 관리 성분'),
    '우레아': ('CH4N2O', None, '보습 성분'),
}
ELEMENTS = {'C': '탄소', 'H': '수소', 'O': '산소', 'N': '질소', 'Na': '나트륨', 'K': '칼륨'}


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
    known = [name for name in names if chemical_info(name)]
    st.subheader('🌱 화학 성분 분석')
    st.caption('통합과학에서 배우는 화학식·구성 원소·산과 염기의 성질을 살펴봅니다. 검증된 일부 성분만 제공해요.')
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
            st.markdown(f'**{selected}: {acid_base}의 성질을 가진 성분**')
            st.write(role + '.')
        else:
            st.info('이 성분은 이 기능에서 산·염기로 분류하지 않았습니다. 중성이라는 판정은 아닙니다.')
        st.caption('개별 원료의 성질만 설명합니다. 전성분표만으로 완제품의 pH나 실제 반응 여부를 판단할 수 없습니다.')
    unknown_count = len(names) - len(known)
    if unknown_count:
        st.caption(f'화학 정보 미제공 성분: {unknown_count}개 (추정하지 않고 제외)')
    st.caption('참고 자료: PubChem (pubchem.ncbi.nlm.nih.gov). 성분별 정보는 교육용이며 실제 배합 특성을 뜻하지 않습니다.')
