import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class WordItem:
    word_id: int
    word: str
    rank: float
    b: float = 0.0
    a: float = 1.0

    def __post_init__(self):
        if self.rank and self.rank > 0:
            self.b = math.log(self.rank)


@dataclass
class AnswerRecord:
    word_id: int
    correct: bool
    b: float
    a: float = 1.0


@dataclass
class CATState:
    theta: float = 6.0
    theta_se: float = float('inf')
    answers: List[AnswerRecord] = field(default_factory=list)
    answered_word_ids: set = field(default_factory=set)
    items_answered: int = 0
    converged: bool = False

    @property
    def info(self) -> float:
        return fisher_information(self.theta, self.answers)

    @property
    def se(self) -> float:
        I = self.info
        return 1.0 / math.sqrt(I) if I > 0 else float('inf')


def p_correct(theta: float, b: float, a: float = 1.0) -> float:
    z = a * (theta - b)
    if z > 20:
        return 1.0
    if z < -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def fisher_information(theta: float, answers: List[AnswerRecord]) -> float:
    total = 0.0
    for ans in answers:
        p = p_correct(theta, ans.b, ans.a)
        total += ans.a ** 2 * p * (1 - p)
    return total


def item_information(theta: float, b: float, a: float = 1.0) -> float:
    p = p_correct(theta, b, a)
    return a ** 2 * p * (1 - p)


def update_theta_mle(
    theta_old: float,
    answers: List[AnswerRecord],
    max_iter: int = 50,
    tol: float = 1e-6,
    theta_min: float = -2.0,
    theta_max: float = 12.0,
) -> Tuple[float, float]:
    theta = theta_old
    for _ in range(max_iter):
        I = fisher_information(theta, answers)
        if I <= 0:
            break
        grad = 0.0
        for ans in answers:
            p = p_correct(theta, ans.b, ans.a)
            grad += ans.a * (ans.correct - p)
        step = grad / I
        theta_new = theta + step
        theta_new = max(theta_min, min(theta_max, theta_new))
        if abs(theta_new - theta) < tol:
            theta = theta_new
            break
        theta = theta_new
    I = fisher_information(theta, answers)
    se = 1.0 / math.sqrt(I) if I > 0 else float('inf')
    return theta, se


def select_next_item(
    theta: float,
    candidate_words: List[WordItem],
) -> Optional[WordItem]:
    if not candidate_words:
        return None
    best = None
    best_info = -1.0
    for w in candidate_words:
        info = item_information(theta, w.b, w.a)
        if info > best_info:
            best_info = info
            best = w
    return best


def theta_to_vocab(theta: float, theta_min: float = 3.0, theta_max: float = 10.5, v_min: int = 20, v_max: int = 20000) -> int:
    if theta <= theta_min:
        return v_min
    if theta >= theta_max:
        return v_max
    ratio = (theta - theta_min) / (theta_max - theta_min)
    v = v_min * (v_max / v_min) ** ratio
    return int(round(v))


def vocab_to_theta(vocab: int, theta_min: float = 3.0, theta_max: float = 10.5, v_min: int = 20, v_max: int = 20000) -> float:
    if vocab <= v_min:
        return theta_min
    if vocab >= v_max:
        return theta_max
    ratio = math.log(vocab / v_min) / math.log(v_max / v_min)
    return theta_min + ratio * (theta_max - theta_min)


def check_stopping(
    state: CATState,
    min_items: int = 5,
    max_items: int = 25,
    se_threshold: float = 0.3,
) -> bool:
    if state.items_answered >= max_items:
        return True
    if state.items_answered < min_items:
        return False
    if state.theta_se <= se_threshold and state.items_answered >= min_items:
        return True
    return False


def compute_cat_result(state: CATState) -> Dict:
    point = theta_to_vocab(state.theta)
    lower = theta_to_vocab(state.theta - state.theta_se)
    upper = theta_to_vocab(state.theta + state.theta_se)
    return {
        "theta": round(state.theta, 4),
        "theta_se": round(state.theta_se, 4),
        "vocab_point": point,
        "vocab_lower": lower,
        "vocab_upper": upper,
        "items_answered": state.items_answered,
        "converged": state.converged,
    }
