from pydantic import BaseModel, Field


class QuestionResponse(BaseModel):
    session_id: int
    question_index: int
    total_questions: int
    word_id: int
    word: str
    definition: str
    level: int


class StartTestResponse(BaseModel):
    session_id: int
    total_questions: int
    first_question: QuestionResponse


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

class BatchAnswer(BaseModel):
    word: str
    known: bool


class RealBatchRequest(BaseModel):
    answers: list[BatchAnswer]
    algorithm: str = "stratified"


class RealBatchLevelBreakdown(BaseModel):
    level: int
    rank_start: int
    rank_end: int
    total_words: int
    sampled_count: int
    known_count: int
    recognition_rate: float
    estimated_known_words: int
    unknown_words: list[str]


class RealBatchResultResponse(BaseModel):
    point_estimate: int
    lower_bound: int
    upper_bound: int
    confidence_level: float
    summary: str
    level_breakdown: list[RealBatchLevelBreakdown]
    matched_count: int
    unmatched_words: list[str]

class TextAnalyzeRequest(BaseModel):
    text: str = Field(..., max_length=10000, description="待分析的英文文档")
    min_recognition_rate: float = Field(0.85, ge=0.5, le=1.0, description="最低认识率假设")


class ReverseLevelBreakdown(BaseModel):
    level: int
    rank_start: int
    rank_end: int
    total_words: int
    document_word_count: int
    document_percentage: float
    min_recognition_rate: float
    estimated_known_words: int


class ReverseVocabEstimate(BaseModel):
    point_estimate: int
    lower_bound: int
    upper_bound: int
    confidence_level: float
    level_breakdown: list[ReverseLevelBreakdown]
    explanation: str
    max_level: int
    total_unique_words: int
    min_recognition_rate: float


class TextAnalyzeResponse(BaseModel):
    total_words: int
    matched_words: int
    vocab_estimate: ReverseVocabEstimate


class CATQuestion(BaseModel):
    word_id: int
    word: str
    definition: str


class CATStartResponse(BaseModel):
    session_id: str
    first_question: CATQuestion


class CATAnswerRequest(BaseModel):
    word_id: int
    response: str = Field(pattern="^(know|unknown)$")


class CATStatus(BaseModel):
    items_answered: int
    theta: float
    theta_se: float
    vocab_point: int
    vocab_lower: int
    vocab_upper: int
    converged: bool


class CATAnswerResponse(BaseModel):
    session_id: str
    finished: bool
    next_question: CATQuestion | None = None
    status: CATStatus


class CATResultResponse(BaseModel):
    session_id: str
    theta: float
    theta_se: float
    point_estimate: int
    lower_bound: int
    upper_bound: int
    items_answered: int
    converged: bool
    summary: str
