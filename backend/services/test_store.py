"""缓存我们测试中抽取到的单词"""

from backend.services.sampler import QuestionItem

_SESSION_QUESTIONS: dict[int, list[QuestionItem]] = {}


def get_session_questions(session_id: int, questions: list[QuestionItem] | None = None):
    if questions is not None:
        _SESSION_QUESTIONS[session_id] = questions
    return _SESSION_QUESTIONS.get(session_id, [])


def save_answer(session_id: int, answer) -> None:
    del session_id, answer