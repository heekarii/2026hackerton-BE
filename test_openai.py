import os
import sys
from dotenv import load_dotenv
from services.openai_analysis import analyze_complaint

def run_test():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    print("=== OpenAI API 민원 분석 기능 테스트 ===")
    if not api_key:
        print("⚠️  경고: .env 파일에 OPENAI_API_KEY가 설정되지 않았습니다.")
        print("테스트를 실행하려면 .env 파일에 OPENAI_API_KEY=your_key 형식을 추가해 주세요.")
        print("또는 아래 예시처럼 Mock 형태로 임시 결과를 출력합니다.\n")
        
        print("입력 예시: '기숙사 3층 온수 배관이 터져서 바닥이 물바다가 되었어요. 빨리 물 좀 잠가주시고 수리해 주세요!'")
        print("\n[Mock 분석 결과 출력]")
        print("category: 시설")
        print("subcategory: 온수 배관 누수")
        print("sentiment: 부정")
        print("urgency: CRITICAL")
        print("sensitive: False")
        print("risk_type: 안전")
        print("department: 시설관리팀")
        print("summary: 기숙사 3층 온수 배관 누수로 인한 침수 상태 고발 및 빠른 잠금/수리 조치 요청")
        print("keywords: ['기숙사', '온수 배관', '누수', '물바다', '수리']")
        print("expected_days: 즉시")
        print("recommended_action: 단수 밸브를 즉시 차단하고 설비팀 긴급 출동 지시")
        return

    # 실제 API 호출 테스트
    sample_text = "기숙사 3층 온수 배관이 터져서 바닥이 물바다가 되었어요. 빨리 물 좀 잠가주시고 수리해 주세요!"
    print(f"입력 텍스트: '{sample_text}'")
    print("OpenAI API 호출 중...")
    
    try:
        result = analyze_complaint(sample_text)
        print("\n✅ OpenAI API 분석 완료! 결과:")
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
        print(f"❌ 분석 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_test()
