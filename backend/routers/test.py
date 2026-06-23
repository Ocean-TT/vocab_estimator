from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.entities import TestAnswer, TestSession
from backend.schemas import (
    AnswerRequest,
    AnswerResponse,
    QuestionResponse,
    ResultResponse,
    StartTestResponse,
)
from backend.services.estimator import estimate_vocabulary
from backend.services.sampler import build_question_set
from backend.services.test_store import get_session_questions, save_answer

router = APIRouter(prefix="/api/test", tags=["test"])


def _to_question(session_id: int, question, index: int, total: int) -> QuestionResponse:
    return QuestionResponse(
        session_id=session_id,
        question_index=index,
        total_questions=total,
        word_id=question.word_id,
        word=question.word,
        definition=question.definition,
        level=question.level,
    )


@router.post("/start", response_model=StartTestResponse)
def start_test(db: Session = Depends(get_db)):
    questions = build_question_set(db)
    if not questions:
        raise HTTPException(status_code=500, detail="词表为空，请先运行 seed 脚本导入数据")

    session = TestSession(status="in_progress", current_index=0)
    db.add(session)
    db.commit()
    db.refresh(session)

    get_session_questions(session.id, questions)

    first = questions[0]
    return StartTestResponse(
        session_id=session.id,
        total_questions=len(questions),
        first_question=_to_question(session.id, first, 0, len(questions)),
    )


@router.post("/{session_id}/answer", response_model=AnswerResponse)
def submit_answer(session_id: int, payload: AnswerRequest, db: Session = Depends(get_db)):
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="测试会话不存在")
    if session.status == "finished":
        raise HTTPException(status_code=400, detail="测试已结束")

    questions = get_session_questions(session_id)
    if not questions:
        raise HTTPException(status_code=404, detail="找不到测试题目")

    index = session.current_index
    if index >= len(questions):
        raise HTTPException(status_code=400, detail="没有更多题目")

    current = questions[index]
    if current.word_id != payload.word_id:
        raise HTTPException(status_code=400, detail="题目与答案不匹配")

    answer = TestAnswer(
        session_id=session_id,
        word_id=payload.word_id,
        response=payload.response,
        question_order=index,
    )
    db.add(answer)
    save_answer(session_id, answer)

    index += 1
    session.current_index = index

    if index >= len(questions):
        session.status = "finished"
        db.commit()
        return AnswerResponse(session_id=session_id, finished=True, next_question=None)

    db.commit()
    next_q = questions[index]
    return AnswerResponse(
        session_id=session_id,
        finished=False,
        next_question=_to_question(session_id, next_q, index, len(questions)),
    )


@router.get("/{session_id}/result", response_model=ResultResponse)
def get_result(session_id: int, db: Session = Depends(get_db)):
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="测试会话不存在")
    if session.status != "finished":
        raise HTTPException(status_code=400, detail="测试尚未完成")

    result = estimate_vocabulary(db, session_id)
    summary = (
        f"估计词汇量 {result.lower_bound}-{result.upper_bound} 词，"
        f"点估计 {result.point_estimate} 词，"
        f"置信度 {int(result.confidence_level * 100)}%"
    )

    return ResultResponse(
        session_id=session_id,
        point_estimate=result.point_estimate,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        confidence_level=result.confidence_level,
        summary=summary,
        level_breakdown=[
            {
                "level": item.level,
                "rank_start": item.rank_start,
                "rank_end": item.rank_end,
                "total_words": item.total_words,
                "known_words": item.known_words,
                "recognition_rate": item.recognition_rate,
            }
            for item in result.level_breakdown
        ],
    )
