import uuid
import math
import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.entities import Word, TestSession, TestAnswer
from backend.services.estimator_cat import (
    CATState, WordItem, AnswerRecord,
    update_theta_mle, select_next_item, check_stopping, compute_cat_result
)


class CATSessionManager:
    def __init__(self):
        self._sessions: Dict[str, CATState] = {}
        self._word_pool: Dict[str, List[WordItem]] = {}
        self._db_session_map: Dict[str, int] = {}

    def create_session(self, db: Session) -> tuple[str, CATState, WordItem]:
        sid = str(uuid.uuid4())
        state = CATState()
        self._sessions[sid] = state

        all_words = self._get_all_words(db)
        self._word_pool[sid] = all_words.copy()

        db_session = TestSession(
            status="in_progress",
            current_index=0,
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        self._db_session_map[sid] = db_session.id

        first_word = select_next_item(state.theta, all_words)
        if first_word:
            self._word_pool[sid] = [w for w in all_words if w.word_id != first_word.word_id]
            state.answered_word_ids.add(first_word.word_id)
        return sid, state, first_word

    def _get_all_words(self, db: Session) -> List[WordItem]:
        rows = (
            db.query(Word.id, Word.word, Word.rank)
            .filter(Word.rank.isnot(None))
            .filter(Word.rank > 0)
            .order_by(func.random())
            .all()
        )
        return [WordItem(word_id=r[0], word=r[1], rank=r[2]) for r in rows]

    def get_state(self, sid: str) -> Optional[CATState]:
        return self._sessions.get(sid)

    def submit_answer(
        self,
        sid: str,
        word_id: int,
        correct: bool,
        db: Session,
    ) -> tuple[Optional[WordItem], bool, dict]:
        state = self._sessions.get(sid)
        if not state:
            return None, False, {}

        rank_row = db.query(Word.rank).filter(Word.id == word_id).first()
        if not rank_row or not rank_row[0]:
            return None, False, {}

        b = math.log(rank_row[0])

        ans = AnswerRecord(word_id=word_id, correct=correct, b=b, a=1.0)
        state.answers.append(ans)
        state.items_answered += 1

        db_session_id = self._db_session_map.get(sid)
        if db_session_id:
            db_answer = TestAnswer(
                session_id=db_session_id,
                word_id=word_id,
                response="know" if correct else "unknown",
                question_order=state.items_answered - 1,
            )
            db.add(db_answer)
            db.commit()

        state.theta, state.theta_se = update_theta_mle(state.theta, state.answers)

        stopped = check_stopping(state)
        state.converged = stopped

        next_word = None
        if not stopped:
            pool = self._word_pool.get(sid, [])
            next_word = select_next_item(state.theta, pool)
            if next_word:
                self._word_pool[sid] = [w for w in pool if w.word_id != next_word.word_id]
                state.answered_word_ids.add(next_word.word_id)
            else:
                stopped = True

        if stopped and db_session_id:
            result_data = compute_cat_result(state)
            db_session = db.query(TestSession).filter(TestSession.id == db_session_id).first()
            if db_session:
                db_session.status = "finished"
                db_session.current_index = state.items_answered
                db.commit()

        return next_word, stopped, compute_cat_result(state)

    def cleanup(self, sid: str):
        self._sessions.pop(sid, None)
        self._word_pool.pop(sid, None)
        self._db_session_map.pop(sid, None)

cat_manager = CATSessionManager()
