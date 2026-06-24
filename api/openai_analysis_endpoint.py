from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from services.openai_analysis import analyze_complaint, ComplaintAnalysis

router = APIRouter(tags=["AI Analysis"])

class ComplaintAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=5, description="분석할 민원 텍스트 (최소 5자 이상)")

@router.post("/analyze", response_model=ComplaintAnalysis, status_code=status.HTTP_200_OK)
def analyze_complaint_endpoint(request: ComplaintAnalysisRequest):
    """
    사용자가 입력한 민원 텍스트를 OpenAI API를 사용하여 카테고리, 감정, 긴급도, 위험 요소 등을 구조화된 JSON으로 분석합니다.
    """
    try:
        analysis_result = analyze_complaint(request.text)
        return analysis_result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenAI 분석 중 오류가 발생했습니다: {str(e)}"
        )
