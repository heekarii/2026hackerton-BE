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

def get_mock_analysis(text: str) -> ComplaintAnalysis:
    """
    OpenAI API를 사용할 수 없거나 Mock 모드가 활성화되었을 때 사용하는 가짜 분석 결과를 생성합니다.
    """
    category = "기타"
    subcategory = "기타 문의 사항"
    sentiment = "중립"
    urgency = "LOW"
    risk_type = "없음"
    department = "학생지원팀"
    expected_days = "3일"
    recommended_action = "접수된 민원의 세부 내용을 검토하여 유관 부서에 협조를 요청하고 처리 과정을 안내합니다."

    # 부정적인 단어가 포함된 경우 감정을 '부정'으로 설정
    negative_words = ["고장", "불만", "더럽", "지저분", "어둡", "위험", "망가", "터짐", "누수", "추워", "더워"]
    if any(word in text for word in negative_words):
        sentiment = "부정"
        urgency = "MEDIUM"

    # 키워드 매핑 기반의 카테고리/부서 추정
    if any(word in text for word in ["에어컨", "온풍기", "난방", "냉방", "히터", "창문", "조명", "배관", "누수", "수리", "고장", "전등", "전구", "전기", "램프"]):
        category = "시설"
        subcategory = "시설물 설비 고장 및 수리 요청"
        department = "시설관리팀"
        urgency = "HIGH" if any(word in text for word in ["누수", "터짐", "바닥이 물바다", "합선"]) else "MEDIUM"
        expected_days = "2일"
        recommended_action = "시설관리팀 설비 담당 직원을 해당 현장에 파견하여 고장 원인을 파악하고 즉각 보수 및 수리 조치를 진행합니다."
        
    elif any(word in text for word in ["쓰레기", "청소", "위생", "화장실", "냄새", "먼지"]):
        category = "청소"
        subcategory = "교내 위생 및 미화 관리 요망"
        department = "총무팀"
        urgency = "MEDIUM"
        expected_days = "1일"
        recommended_action = "해당 구역의 미화 담당 직원에게 현장 상태를 전달하여 쓰레기 수거 및 위생 소독 작업을 즉각 지시합니다."
        
    elif any(word in text for word in ["경비", "도둑", "수상한", "cctv", "CCTV", "보안", "잠금", "순찰", "안전"]):
        category = "보안"
        subcategory = "방범 및 안전 보안 요청"
        department = "종합상황실/보안팀"
        urgency = "HIGH"
        expected_days = "즉시"
        recommended_action = "종합상황실 보안 담당자에게 인근 CCTV 확인을 지시하고, 보안 요원을 긴급 파견하여 주변 보안 순찰을 대폭 강화합니다."
        
    elif any(word in text for word in ["수강", "성적", "장학", "등록금", "졸업", "휴학", "강의"]):
        category = "수업"
        subcategory = "학사 지원 및 수강 행정 문의"
        department = "학사지원팀"
        urgency = "LOW"
        expected_days = "3일"
        recommended_action = "학사 담당자가 해당 학생의 학적 상태 및 수강 신청 데이터를 조회하여 상세 해결 방안을 개별 안내합니다."
        
    elif any(word in text for word in ["학생회", "복지", "학생증", "동아리"]):
        category = "복지"
        subcategory = "학생 복지 서비스 문의"
        department = "학생지원팀"
        urgency = "LOW"
        expected_days = "5일"
        recommended_action = "학생지원팀 복지 담당자가 접수된 건의 사항의 실현 가능성 및 예산 여부를 내부 검토합니다."

    # 긴급/위험 단어가 감지되면 긴급도를 격상하고 위험 유형 설정
    if any(word in text for word in ["싸움", "폭행", "폭력"]):
        urgency = "CRITICAL"
        risk_type = "폭력"
        recommended_action = "보안팀과 학생과 담당 직원이 즉시 출동하여 현장을 제지하고 사실 관계 조사 및 가해자 분리 조치를 취합니다."
    elif any(word in text for word in ["성희롱", "성추행"]):
        urgency = "CRITICAL"
        risk_type = "성희롱"
        recommended_action = "양성평등센터 및 담당 인권 기구에 즉시 이관하여 피해자 보호 절차를 개시하고 상담을 지원합니다."
    elif any(word in text for word in ["개인정보", "비밀번호", "학번 노출"]):
        urgency = "HIGH"
        risk_type = "개인정보"
        recommended_action = "개인정보 유출 차단을 위해 정보화 서비스 내 노출된 페이지를 차단하거나 마스킹 처리하고 대상 학생에게 유출 사실을 고지합니다."

    summary = text[:40] + "..." if len(text) > 40 else text
    
    # 핵심 키워드 간단 추출
    keywords = [category, subcategory.split()[0]]
    if len(text.split()) > 2:
        keywords.extend([w.strip("!,.") for w in text.split()[:2] if len(w) > 1])
    keywords = list(dict.fromkeys(keywords))[:5] # 중복 제거

    return ComplaintAnalysis(
        category=category,
        subcategory=subcategory,
        sentiment=sentiment,
        urgency=urgency,
        sensitive=(risk_type != "없음"),
        risk_type=risk_type,
        department=department,
        summary=f"[MOCK] {summary}",
        keywords=keywords,
        expected_days=expected_days,
        recommended_action=recommended_action
    )

def analyze_complaint(text: str) -> ComplaintAnalysis:
    """
    OpenAI Chat API를 활용하여 민원 텍스트를 구조화된 데이터 형태로 분석합니다.
    만약 USE_MOCK_AI=true 이거나 실제 API 호출이 실패할 경우 Mock 응답으로 대체됩니다.
    """
    # .env 파일을 동적으로 다시 로드하여 런타임 중의 변경 사항을 반영합니다.
    load_dotenv(override=True)
    
    # Mock AI 모드 여부 확인
    use_mock = os.getenv("USE_MOCK_AI", "false").lower() in ("true", "1", "t", "y", "yes")
    
    if use_mock:
        print("[AI Analysis] USE_MOCK_AI가 설정되어 Mock 분석 결과를 반환합니다.")
        return get_mock_analysis(text)
        
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[AI Analysis] 경고: OPENAI_API_KEY 환경 변수가 없습니다. Mock 모드로 대체하여 결과를 반환합니다.")
        return get_mock_analysis(text)
    
    try:
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
    except Exception as e:
        print(f"[AI Analysis] 에러 발생: OpenAI API 호출 실패 ({e}). Mock 모드로 대체하여 결과를 반환합니다.")
        return get_mock_analysis(text)
