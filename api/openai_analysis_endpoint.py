from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import get_db
from models import Complaint, ComplaintAttachment
from schemas import ImageAnalysisRequest, ImageAnalysisResponse
from services.openai_analysis import analyze_complaint, ComplaintAnalysis, analyze_image

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

@router.post("/analyze-image", response_model=ImageAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_image_endpoint(request: ImageAnalysisRequest, db: Session = Depends(get_db)):
    """
    OpenAI Vision API를 사용하여 이미지(URL)를 시설 파손, 쓰레기, 위험 요소, 청결 문제 등으로 자동 분류하고 분석합니다.
    complaint_id가 주어지면 DB의 해당 민원 첨부파일 레코드에 분석 결과를 업데이트하거나 새로 저장합니다.
    """
    try:
        # 1. 이미지 분석 수행
        analysis_result = analyze_image(request.image_url)
        
        # 2. complaint_id가 전달된 경우 DB 저장 처리
        if request.complaint_id is not None:
            # 해당 민원이 실제로 존재하는지 확인
            complaint = db.scalar(select(Complaint).where(Complaint.id == request.complaint_id))
            if not complaint:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ID가 {request.complaint_id}인 민원을 찾을 수 없습니다."
                )
            
            # 해당 민원의 첨부파일 중 image_url과 일치하는 항목이 있는지 확인
            attachment = db.scalar(
                select(ComplaintAttachment)
                .where(
                    ComplaintAttachment.complaint_id == request.complaint_id,
                    ComplaintAttachment.file_url == request.image_url
                )
            )
            
            if attachment:
                # 기존 첨부파일 레코드가 있으면 필드 업데이트
                attachment.image_category = analysis_result.image_category
                attachment.detected_objects = analysis_result.detected_objects
                attachment.danger_level = analysis_result.danger_level
                attachment.image_description = analysis_result.image_description
                attachment.photo_based_category_hint = analysis_result.photo_based_category_hint
                attachment.recommended_action = analysis_result.recommended_action
            else:
                # 없으면 신규 첨부파일 레코드 작성
                file_type = "image/jpeg"
                if request.image_url.endswith(".png"):
                    file_type = "image/png"
                elif request.image_url.endswith(".gif"):
                    file_type = "image/gif"
                
                attachment = ComplaintAttachment(
                    complaint_id=request.complaint_id,
                    file_url=request.image_url,
                    file_type=file_type,
                    image_category=analysis_result.image_category,
                    detected_objects=analysis_result.detected_objects,
                    danger_level=analysis_result.danger_level,
                    image_description=analysis_result.image_description,
                    photo_based_category_hint=analysis_result.photo_based_category_hint,
                    recommended_action=analysis_result.recommended_action
                )
                db.add(attachment)
            
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"분석 결과 DB 저장 중 오류가 발생했습니다: {str(e)}"
                )
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 분석 처리 중 오류가 발생했습니다: {str(e)}"
        )

