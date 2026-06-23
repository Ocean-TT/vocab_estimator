from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rank: Mapped[int] = mapped_column(Integer, index=True)
    level: Mapped[int] = mapped_column(Integer, index=True)
    definition: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<Word {self.word} L{self.level}>"


class TestSession(Base):
    __tablename__ = "test_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    answers: Mapped[list["TestAnswer"]] = relationship(back_populates="session")


class TestAnswer(Base):
    __tablename__ = "test_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"))
    response: Mapped[str] = mapped_column(String(20))  # know / unknown / unsure
    question_order: Mapped[int] = mapped_column(Integer)

    session: Mapped["TestSession"] = relationship(back_populates="answers")
    word: Mapped["Word"] = relationship()
