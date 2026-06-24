from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.config import LEVEL_RANGES, QUESTIONS_PER_LEVEL
from backend.models.entities import Word


@dataclass
class QuestionItem:
    word_id: int
    word: str
    definition: str
    level: int
    order: int


def build_question_set(db: Session) -> list[QuestionItem]:
    """从每个词汇层级随机抽取固定数量单词测试"""
    questions: list[QuestionItem] = []
    order = 0

    for level, start_rank, end_rank in LEVEL_RANGES:
        sampled = (
            db.query(Word)
            .filter(Word.rank >= start_rank, Word.rank <= end_rank) # 过滤指定层级的单词
            .order_by(func.random())  # 随机抽取固定数量的单词
            .limit(QUESTIONS_PER_LEVEL)
            .all()
        )
        for item in sampled:
            questions.append(
                QuestionItem(
                    word_id=item.id,
                    word=item.word,
                    definition=item.definition,
                    level=item.level,
                    order=order,
                )
            )
            order += 1

    return questions
