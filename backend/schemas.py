from pydantic import BaseModel, Field


class StartTestResponse(BaseModel):
    session_id: int
    total_questions: int
    first_question: "QuestionResponse"


class QuestionResponse(BaseModel):
    session_id: int
    question_index: int
    total_questions: int
    word_id: int
    word: str
    definition: str
    level: int


class AnswerRequest(BaseModel):
    word_id: int
    response: str = Field(pattern="^(know|unknown|unsure)$")


class AnswerResponse(BaseModel):
    session_id: int
    finished: bool
    next_question: QuestionResponse | None = None


class LevelBreakdownItem(BaseModel):
    level: int
    rank_start: int
    rank_end: int
    total_words: int
    known_words: int
    recognition_rate: float


class ResultResponse(BaseModel):
    session_id: int
    point_estimate: int
    lower_bound: int
    upper_bound: int
    confidence_level: float
    summary: str
    level_breakdown: list[LevelBreakdownItem]


class BatchProfile(BaseModel):
    name: str
    know_rate_by_level: dict[int, float]


class BatchEstimateItem(BaseModel):
    profile: str
    point_estimate: int
    lower_bound: int
    upper_bound: int
    confidence_level: float


class BatchEstimateResponse(BaseModel):
    results: list[BatchEstimateItem]
