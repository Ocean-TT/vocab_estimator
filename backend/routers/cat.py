from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas import (
    CATStartResponse, CATAnswerRequest, CATAnswerResponse,
    CATResultResponse, CATStatus, CATQuestion
)
from backend.services.cat_session import cat_manager
from backend.services.estimator_cat import compute_cat_result
from backend.models.entities import Word, TestSession

router = APIRouter(prefix="/api/cat", tags=["CAT 自适应测试"])

@router.post("/start", response_model=CATStartResponse)
def start_cat_test(db: Session = Depends(get_db)):
    sid, state, first_word = cat_manager.create_session(db)
    if not first_word:
        raise HTTPException(status_code=500, detail="词库为空")
    word = db.query(Word).filter(Word.id == first_word.word_id).first()
    definition = word.definition if word and word.definition else ""
    return CATStartResponse(
        session_id=sid,
        first_question=CATQuestion(
            word_id=first_word.word_id,
            word=first_word.word,
            definition=definition,
        ),
    )

@router.post("/{session_id}/answer", response_model=CATAnswerResponse)
def submit_cat_answer(
    session_id: str,
    req: CATAnswerRequest,
    db: Session = Depends(get_db),
):
    state = cat_manager.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")
    correct = req.response == "know"
    next_word, stopped, result_data = cat_manager.submit_answer(
        session_id, req.word_id, correct, db
    )
    next_question = None
    if next_word:
        word = db.query(Word).filter(Word.id == next_word.word_id).first()
        definition = word.definition if word and word.definition else ""
        next_question = CATQuestion(
            word_id=next_word.word_id,
            word=next_word.word,
            definition=definition,
        )
    status = CATStatus(
        items_answered=result_data["items_answered"],
        theta=result_data["theta"],
        theta_se=result_data["theta_se"],
        vocab_point=result_data["vocab_point"],
        vocab_lower=result_data["vocab_lower"],
        vocab_upper=result_data["vocab_upper"],
        converged=result_data["converged"],
    )
    return CATAnswerResponse(
        session_id=session_id,
        finished=stopped,
        next_question=next_question,
        status=status,
    )


@router.get("/{session_id}/status", response_model=CATStatus)
def get_cat_status(session_id: str):
    state = cat_manager.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")
    result = compute_cat_result(state)
    return CATStatus(
        items_answered=result["items_answered"],
        theta=result["theta"],
        theta_se=result["theta_se"],
        vocab_point=result["vocab_point"],
        vocab_lower=result["vocab_lower"],
        vocab_upper=result["vocab_upper"],
        converged=result["converged"],
    )


@router.get("/{session_id}/result", response_model=CATResultResponse)
def get_cat_result(session_id: str, db: Session = Depends(get_db)):
    state = cat_manager.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在或已过期，请重新测试")
    result_data = compute_cat_result(state)
    point = result_data["vocab_point"]
    lower = result_data["vocab_lower"]
    upper = result_data["vocab_upper"]
    items = result_data["items_answered"]
    return CATResultResponse(
        session_id=session_id,
        theta=result_data["theta"],
        theta_se=result_data["theta_se"],
        point_estimate=point,
        lower_bound=lower,
        upper_bound=upper,
        items_answered=items,
        converged=result_data["converged"],
        summary=f"经过 {items} 道自适应题测试，您的词汇量约为 {point} 词（90%置信区间：{lower}-{upper}）",
    )
