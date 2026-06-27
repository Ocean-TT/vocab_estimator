from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas import TextAnalyzeRequest, TextAnalyzeResponse
from backend.services.text_analyzer import analyze_text_auto

router = APIRouter(prefix="/api/text", tags=["文档词汇量分析"])


@router.post("/analyze", response_model=TextAnalyzeResponse)
def analyze_text(req: TextAnalyzeRequest, db: Session = Depends(get_db)):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")
    
    result = analyze_text_auto(req.text, req.min_recognition_rate, db)
    
    return TextAnalyzeResponse(
        total_words=result["total_unique_words"],
        matched_words=result["matched_words"],
        vocab_estimate=result["vocab_estimate"],
    )
