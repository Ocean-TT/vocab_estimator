"""初始化数据库并导入示例词表。"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import DATA_DIR, LEVEL_RANGES  # noqa: E402
from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.models.entities import Word  # noqa: E402

def rank_to_level(rank: int) -> int:
    for level, start_rank, end_rank in LEVEL_RANGES:
        if start_rank <= rank <= end_rank:
            return level
    return LEVEL_RANGES[-1][0]

def load_words_from_csv(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row["rank"])
            rows.append(
                {
                    "word": row["word"].strip(),
                    "rank": rank,
                    "level": rank_to_level(rank),
                    "definition": row.get("definition", "").strip(),
                }
            )
    return rows

def seed():
    Base.metadata.create_all(bind=engine)
    coca_path = DATA_DIR / "coca_20000.csv"
    payload = load_words_from_csv(coca_path)
    db = SessionLocal()
    try:
        db.query(Word).delete()
        db.add_all([Word(**item) for item in payload])
        db.commit()
        print(f"Imported {len(payload)} words.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
