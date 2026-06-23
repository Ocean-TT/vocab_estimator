from dataclasses import dataclass

from sqlalchemy.orm import Session

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
    """从每个词汇层级随机抽取固定数量单词，组成测试题集。"""
    questions: list[QuestionItem] = []
    order = 0

    for level, start_rank, end_rank in LEVEL_RANGES:
        words = (
            db.query(Word)
            .filter(Word.rank >= start_rank, Word.rank <= end_rank)
            .order_by(Word.id)
            .all()
        )
        if not words:
            continue

        sample_size = min(QUESTIONS_PER_LEVEL, len(words))
        # SQLite 使用 random() 做简单抽样
        sampled = (
            db.query(Word)
            .filter(Word.rank >= start_rank, Word.rank <= end_rank)
            .order_by(Word.id)  # 骨架阶段先用确定性顺序，便于调试
            .limit(sample_size)
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
