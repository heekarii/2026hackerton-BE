import os
import sys
from dotenv import load_dotenv
from services.openai_analysis import analyze_complaint

def run_test():
    load_dotenv(override=True)
    use_mock = os.getenv("USE_MOCK_AI", "false").lower() in ("true", "1", "t", "y", "yes")
    api_key = os.getenv("OPENAI_API_KEY")
    
    print("=== OpenAI API 민원 분석 기능 테스트 ===")
    print(f"설정 상태: USE_MOCK_AI={use_mock}, OPENAI_API_KEY={'설정됨' if api_key else '설정안됨'}")
    
    sample_text = "기숙사 3층 온수 배관이 터져서 바닥이 물바다가 되었어요. 빨리 물 좀 잠가주시고 수리해 주세요!"
    print(f"테스트 입력 텍스트: '{sample_text}'")
    print("분석 함수 호출 중...")
    
    try:
        result = analyze_complaint(sample_text)
        print("\n✅ 분석 함수 호출 성공! 반환된 객체:")
        print(f"  - category: {result.category}")
        print(f"  - subcategory: {result.subcategory}")
        print(f"  - sentiment: {result.sentiment}")
        print(f"  - urgency: {result.urgency}")
        print(f"  - sensitive: {result.sensitive}")
        print(f"  - risk_type: {result.risk_type}")
        print(f"  - department: {result.department}")
        print(f"  - summary: {result.summary}")
        print(f"  - keywords: {result.keywords}")
        print(f"  - expected_days: {result.expected_days}")
        print(f"  - recommended_action: {result.recommended_action}")
        
    except Exception as e:
        print(f"❌ 예외 발생 (에러 처리 실패): {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_test()
