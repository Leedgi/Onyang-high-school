"""A 초안 → 자동 선택 기록 → B 요청. 미식별은 분석에서 제외하고 원문은 보존한다."""
import re

from core.normalize import normalize_key
from shared.contracts import AutomaticDecision


def identity_marks(name):
    return re.findall(r'\d+|nano|나노|/', normalize_key(name).casefold())


def resolve_automatically(drafts, database):
    decisions=[]
    for draft in drafts:
        if draft.status in {'exact','alias'} and database.find(draft.name):
            decisions.append(AutomaticDecision(draft,database.find(draft.name).name,100.0,'DB 이름 일치'))
            continue
        candidates=sorted(draft.candidates,key=lambda c:(-c.score,c.name))
        selected=next((c for c in candidates if c.score>=60 and database.find(c.name)
                       and len(normalize_key(draft.raw_text))>=3
                       and identity_marks(draft.raw_text)==identity_marks(c.matched_name)),None)
        if selected:
            decisions.append(AutomaticDecision(draft,selected.name,selected.score,
                '가장 가까운 이름을 자동 추정 선택 · 유사도는 정답 확률이 아님'))
        else:
            decisions.append(AutomaticDecision(draft,reason='DB 이름 미식별·유사도 부족·숫자/표기 충돌로 제외'))
    return tuple(decisions)
