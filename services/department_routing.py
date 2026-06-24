from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class DepartmentRule:
    name: str
    description: str
    keywords: Tuple[str, ...]
    aliases: Tuple[str, ...] = ()


DEPARTMENT_RULES: Tuple[DepartmentRule, ...] = (
    DepartmentRule(
        name="시설관리팀",
        description="교내 건물, 설비, 전기, 수도 및 시설물 유지보수",
        keywords=(
            "시설", "에어컨", "냉방", "난방", "엘리베이터", "전기", "정전",
            "수도", "누수", "조명", "화장실", "건물", "고장", "주차",
            "도로", "보도", "문", "창문", "책상", "의자",
        ),
        aliases=("시설관리처", "시설팀", "시설과"),
    ),
    DepartmentRule(
        name="정보통신팀",
        description="교내 네트워크, 전산 시스템 및 정보 서비스 운영",
        keywords=(
            "와이파이", "wifi", "인터넷", "네트워크", "서버", "홈페이지",
            "앱", "전산", "프린터", "로그인", "계정", "정보시스템",
        ),
        aliases=("전산팀", "정보화팀", "정보통신처"),
    ),
    DepartmentRule(
        name="학사지원팀",
        description="수강, 성적, 학점, 졸업 등 학사 행정 지원",
        keywords=(
            "수강", "수강신청", "성적", "학점", "졸업", "등록금", "강의",
            "시험", "출결", "학사", "휴학", "복학", "증명서",
        ),
        aliases=("학사팀", "교무팀", "교무처"),
    ),
    DepartmentRule(
        name="학생지원팀",
        description="학생 복지, 장학, 상담 및 학생 활동 지원",
        keywords=(
            "장학금", "학생증", "동아리", "상담", "복지", "학생회",
            "취업", "진로", "봉사", "학생지원", "민원",
        ),
        aliases=("학생처", "학생지원처"),
    ),
    DepartmentRule(
        name="총무팀",
        description="교내 청소, 위생, 환경 및 일반 행정 관리",
        keywords=(
            "청소", "쓰레기", "분리수거", "위생", "방역", "악취", "먼지",
            "환경", "소음", "흡연", "미화",
        ),
        aliases=("총무처", "환경미화팀"),
    ),
    DepartmentRule(
        name="보안팀",
        description="교내 방범, 출입 통제 및 안전사고 대응",
        keywords=(
            "cctv", "도난", "폭행", "범죄", "경비", "보안", "출입",
            "안전", "위험", "화재", "비상", "순찰",
        ),
        aliases=("경비실", "종합상황실", "안전관리팀"),
    ),
    DepartmentRule(
        name="인권센터",
        description="인권 침해, 차별, 괴롭힘 및 성 관련 피해 상담",
        keywords=(
            "성희롱", "성폭력", "차별", "괴롭힘", "인권", "혐오", "폭언",
            "갑질", "스토킹", "신고",
        ),
        aliases=("인권상담센터", "성평등센터"),
    ),
    DepartmentRule(
        name="생활관",
        description="기숙사 시설과 생활 관련 민원 처리",
        keywords=(
            "기숙사", "생활관", "룸메이트", "사감", "기숙사비", "호실",
            "점호", "외박", "세탁실",
        ),
        aliases=("기숙사행정실", "생활관행정실"),
    ),
)

DEFAULT_DEPARTMENT_NAME = "학생지원팀"


@dataclass(frozen=True)
class DepartmentMatch:
    rule: DepartmentRule
    score: int
    confidence: float
    matched_keywords: Tuple[str, ...]


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def get_department_rule(name_or_alias: str) -> Optional[DepartmentRule]:
    normalized = normalize_text(name_or_alias)
    for rule in DEPARTMENT_RULES:
        candidates = (rule.name,) + rule.aliases
        if any(normalize_text(candidate) == normalized for candidate in candidates):
            return rule
    return None


def match_departments(
    texts: Sequence[Optional[str]],
    suggested_department: Optional[str] = None,
    limit: int = 3,
) -> List[DepartmentMatch]:
    combined_text = normalize_text(" ".join(text for text in texts if text))
    suggested_rule = (
        get_department_rule(suggested_department)
        if suggested_department
        else None
    )

    raw_matches = []
    for rule in DEPARTMENT_RULES:
        matched_keywords = tuple(
            keyword
            for keyword in rule.keywords
            if normalize_text(keyword) in combined_text
        )
        score = len(matched_keywords)
        if suggested_rule and suggested_rule.name == rule.name:
            score += 3
        raw_matches.append((rule, score, matched_keywords))

    raw_matches.sort(key=lambda item: (-item[1], item[0].name))
    highest_score = raw_matches[0][1] if raw_matches else 0

    if highest_score == 0:
        default_rule = get_department_rule(DEFAULT_DEPARTMENT_NAME)
        if default_rule is None:
            return []
        return [
            DepartmentMatch(
                rule=default_rule,
                score=0,
                confidence=0.0,
                matched_keywords=(),
            )
        ]

    matches = []
    for rule, score, matched_keywords in raw_matches[: max(1, limit)]:
        if score == 0:
            continue
        confidence = round(score / highest_score, 2)
        matches.append(
            DepartmentMatch(
                rule=rule,
                score=score,
                confidence=confidence,
                matched_keywords=matched_keywords,
            )
        )
    return matches
