import os
from typing import List
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# .env 파일 로드
load_dotenv()

class ComplaintAnalysis(BaseModel):
    category: str = Field(..., description="민원 카테고리. '시설', '청소', '보안', '수업', '행정', '복지', '기타' 중 하나만 선택해야 합니다.")
    subcategory: str = Field(..., description="세부 카테고리 (예: 에어컨 고장, 화장실 청소 불량, 수강신청 등 구체적인 세부 주제)")
    sentiment: str = Field(..., description="민원 텍스트의 감정 상태. '긍정', '중립', '부정' 중 하나만 선택해야 합니다.")
    urgency: str = Field(..., description="긴급도. 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL' 중 하나만 선택해야 합니다.")
    sensitive: bool = Field(..., description="개인정보 노출, 심각한 폭언, 민감하거나 은밀한 개인 사정 등 포함 여부 (true 또는 false)")
    risk_type: str = Field(..., description="위험 유형. '안전', '폭력', '성희롱', '개인정보', '차별', '범죄', '없음' 중 하나만 선택해야 합니다.")
    department: str = Field(..., description="민원을 처리할 추천 담당 부서 (예: 시설관리팀, 학생지원팀, 학사지원팀, 총무팀, 정보통신팀 등)")
    summary: str = Field(..., description="관리자를 위해 작성된 민원 내용 한 줄 요약")
    keywords: List[str] = Field(..., description="핵심 키워드 3~5개의 배열")
    expected_days: str = Field(..., description="민원 해결을 위해 예상되는 대략적인 처리 기간 (예: '1일', '3일', '1주일', '즉시' 등)")
    recommended_action: str = Field(..., description="관리자가 이 민원을 해결하기 위해 신속하게 조치해야 할 추천 가이드라인")

def analyze_complaint(text: str) -> ComplaintAnalysis:
    """
    OpenAI Chat API를 활용하여 민원 텍스트를 구조화된 데이터 형태로 분석합니다.
    """
    # .env 파일을 동적으로 다시 로드하여 런타임 중의 변경 사항을 반영합니다.
    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인해 주세요.")
    
    # client 생성
    client = OpenAI(api_key=api_key)
    
    # Structured Outputs API 호출
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 캠퍼스 민원을 정밀하게 분석하여 분류하고 요약하는 행정 보조 AI 전문가입니다."},
            {"role": "user", "content": f"다음 민원 텍스트를 분석하여 지정된 형식으로 반환해 주세요:\n\n[민원 내용]\n{text}"}
        ],
        response_format=ComplaintAnalysis,
        temperature=0.0
    )
    
    return completion.choices[0].message.parsed
