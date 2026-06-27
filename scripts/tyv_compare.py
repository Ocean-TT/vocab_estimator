"""
testyourvocab.com (Preply) 对比验证脚本。

通过 GraphQL API 直接与 testyourvocab 交互，模拟不同认识率下的答题过程，
对比 TYY 分数和我们的估算值，验证算法准确性。

用法：
    python scripts/tyv_compare.py -o results.csv
    python scripts/tyv_compare.py -o results.csv --ratios 0.3 0.5 0.7 --reps 20
"""

import argparse
import asyncio
import csv
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from playwright.async_api import async_playwright

from backend.database import SessionLocal
from backend.models.entities import Word
from backend.services.estimator import estimate_from_level_responses

TYY_URL = "https://preply.com/en/learn/english/test-your-vocab"
GRAPHQL_URL = "https://preply.com/graphql/"

QUERIES = {
    "TestYourVocabCalculateMidpoint": """
        query TestYourVocabCalculateMidpoint($answers: [TestYourVocabAnswerInput!]) {
            testyourvocabCalculateMidpoint(answers: $answers)
        }
    """,
    "TestYourVocabStepTwoWords": """
        query TestYourVocabStepTwoWords($midpoint: Int!) {
            testyourvocabStepTwoWords(midpoint: $midpoint) {
                value
                word_id
            }
        }
    """,
    "TestYourVocabCalculateMidpointFinal": """
        query TestYourVocabCalculateMidpointFinal($answers: [TestYourVocabAnswerInput!]) {
            testyourvocabCalculateMidpointFinal(answers: $answers) {
                resultHash
                score
            }
        }
    """,
}


async def get_step1_words(page, max_retries=5):
    for attempt in range(max_retries):
        try:
            words = await page.evaluate(
                """() => {
                    if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props 
                        && window.__NEXT_DATA__.props.pageProps 
                        && window.__NEXT_DATA__.props.pageProps.testYourVocabWords) {
                        return window.__NEXT_DATA__.props.pageProps.testYourVocabWords;
                    }
                    return null;
                }"""
            )
            if words and len(words) > 0:
                return words
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        await page.reload(wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
    raise RuntimeError("无法获取 step1 单词列表，请检查网络连接或页面是否变化")


async def call_graphql(page, operation_name, variables):
    payload = {
        "operationName": operation_name,
        "variables": variables,
        "query": QUERIES[operation_name],
    }
    result = await page.evaluate(
        """(p) => fetch('https://preply.com/graphql/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(p),
        }).then(r => r.json())""",
        payload,
    )
    if "data" not in result or result["data"] is None:
        raise RuntimeError(f"GraphQL {operation_name} failed: {result}")
    return result["data"]


def make_answers(words, ratio, seed):
    random.seed(seed)
    n = len(words)
    known_count = round(n * ratio)
    indices = set(random.sample(range(n), known_count))
    return [
        {"wordId": w["word_id"], "known": i in indices}
        for i, w in enumerate(words)
    ]


def compute_our_estimate(step1_words, step2_words, ans1, ans2):
    db: Session = SessionLocal()
    try:
        all_words = step1_words + step2_words
        all_answers = ans1 + ans2

        level_responses = {}
        level_sampled = {}
        level_known = {}
        not_found = 0
        found_words = []

        for w, a in zip(all_words, all_answers):
            word_lower = w["value"].strip().lower()
            word_obj = db.query(Word).filter(Word.word == word_lower).first()
            if word_obj is None:
                not_found += 1
                continue

            found_words.append(word_lower)
            lvl = word_obj.level
            level_responses.setdefault(lvl, []).append(a["known"])
            level_sampled[lvl] = level_sampled.get(lvl, 0) + 1
            if a["known"]:
                level_known[lvl] = level_known.get(lvl, 0) + 1

        result = estimate_from_level_responses(level_responses)

        found = len(found_words)
        coverage = round(found / len(all_words), 3) if len(all_words) > 0 else 0.0

        level_dist = {}
        level_ratios = {}
        for lvl in sorted(level_sampled.keys()):
            level_dist[f"L{lvl}"] = level_sampled[lvl]
            t = level_sampled[lvl]
            k = level_known.get(lvl, 0)
            level_ratios[f"L{lvl}"] = round(k / t, 3) if t > 0 else 0.0

        return {
            "our_estimate": result.point_estimate,
            "our_lower": result.lower_bound,
            "our_upper": result.upper_bound,
            "found_in_db": found,
            "not_in_db": not_found,
            "db_coverage": coverage,
            "level_distribution": json.dumps(level_dist, ensure_ascii=False),
            "level_known_ratios": json.dumps(level_ratios, ensure_ascii=False),
        }
    finally:
        db.close()


async def run_scenario(page, ratio, seed_start, run_id):
    step1_words = await get_step1_words(page)
    ans1 = make_answers(step1_words, ratio, seed_start)
    data1 = await call_graphql(page, "TestYourVocabCalculateMidpoint", {"answers": ans1})
    midpoint = data1["testyourvocabCalculateMidpoint"]
    data2 = await call_graphql(page, "TestYourVocabStepTwoWords", {"midpoint": midpoint})
    step2_words = data2["testyourvocabStepTwoWords"]
    ans2 = make_answers(step2_words, ratio, seed_start + 10000)
    data3 = await call_graphql(page, "TestYourVocabCalculateMidpointFinal", {"answers": ans2})
    score = data3["testyourvocabCalculateMidpointFinal"]["score"]
    info = compute_our_estimate(step1_words, step2_words, ans1, ans2)
    total_words = len(step1_words) + len(step2_words)
    known_words = sum(1 for a in ans1 + ans2 if a["known"])
    diff = info["our_estimate"] - score
    diff_pct = round(diff / score * 100, 1) if score > 0 else 0
    return {
        "run_id": run_id,
        "ratio": ratio,
        "total_words": total_words,
        "known_words": known_words,
        "tyy_score": score,
        "our_estimate": info["our_estimate"],
        "our_lower": info["our_lower"],
        "our_upper": info["our_upper"],
        "diff": diff,
        "diff_pct": diff_pct,
        "found_in_db": info["found_in_db"],
        "not_in_db": info["not_in_db"],
        "db_coverage": info["db_coverage"],
        "level_distribution": info["level_distribution"],
        "level_known_ratios": info["level_known_ratios"],
    }


async def main_async(args):
    ratios = args.ratios if args.ratios else [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
    reps = args.reps

    print(f"启动对比实验: {len(ratios)} 个比例 x {reps} 次重复 = {len(ratios) * reps} 次实验")
    print(f"输出文件: {args.output}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)
        page = await browser.new_page()
        print("正在加载页面...")
        await page.goto(TYY_URL, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(3000)
        print("页面加载完成，开始实验...")
        print()

        rows = []
        run_id = 0
        for ratio in ratios:
            print(f"比例 {ratio*100:.0f}% ({reps} 次实验):")
            for rep in range(reps):
                seed = int(ratio * 100000) + rep
                try:
                    row = await run_scenario(page, ratio, seed, run_id)
                    rows.append(row)
                    run_id += 1
                    print(f"  第 {rep+1}/{reps} 次: TYY={row['tyy_score']}, "
                          f"Our={row['our_estimate']}, Diff={row['diff']:+d} ({row['diff_pct']:+.1f}%)")
                except Exception as e:
                    print(f"  第 {rep+1}/{reps} 次: 失败 - {e}")
            print()

        await browser.close()

    fieldnames = [
        "run_id", "ratio", "total_words", "known_words",
        "tyy_score", "our_estimate", "our_lower", "our_upper",
        "diff", "diff_pct",
        "found_in_db", "not_in_db", "db_coverage",
        "level_distribution", "level_known_ratios",
    ]
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    if not rows:
        print("没有成功的实验结果")
        return

    tyy_scores = [r["tyy_score"] for r in rows]
    ours = [r["our_estimate"] for r in rows]
    abs_diffs = [abs(r["diff"]) for r in rows]
    abs_pcts = [abs(r["diff_pct"]) for r in rows]

    print("=" * 60)
    print(f"完成. 共 {len(rows)} 次成功实验 -> {args.output}")
    print("=" * 60)
    print(f"平均 TYY 分数:    {statistics.mean(tyy_scores):.0f}")
    print(f"平均我们的估算:   {statistics.mean(ours):.0f}")
    print(f"平均绝对差值:     {statistics.mean(abs_diffs):.0f}")
    print(f"平均相对误差:     {statistics.mean(abs_pcts):.1f}%")
    print(f"差值标准差:       {statistics.stdev(abs_diffs):.0f}" if len(abs_diffs) > 1 else "")

    print()
    print("各比例平均对比:")
    print(f"{'比例':>6} {'实验数':>6} {'TYY均值':>8} {'我们均值':>8} {'平均差值':>8} {'相对误差':>8}")
    print("-" * 60)
    for ratio in sorted(set(r["ratio"] for r in rows)):
        subset = [r for r in rows if r["ratio"] == ratio]
        if not subset:
            continue
        avg_tyy = statistics.mean(r["tyy_score"] for r in subset)
        avg_our = statistics.mean(r["our_estimate"] for r in subset)
        avg_diff = statistics.mean(r["diff"] for r in subset)
        avg_abs_pct = statistics.mean(abs(r["diff_pct"]) for r in subset)
        print(f"{ratio*100:>5.0f}% {len(subset):>6} {avg_tyy:>8.0f} {avg_our:>8.0f} "
              f"{avg_diff:>+8.0f} {avg_abs_pct:>7.1f}%")


def main():
    parser = argparse.ArgumentParser(description="testyourvocab.com 对比验证脚本")
    parser.add_argument("-o", "--output", required=True, help="输出 CSV 文件路径")
    parser.add_argument("--ratios", type=float, nargs="+",
                        default=[0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0],
                        help="认识率列表 (默认: 0.0 0.1 0.2 0.3 0.5 0.7 0.9 1.0)")
    parser.add_argument("--reps", type=int, default=10,
                        help="每个比例的重复实验次数 (默认: 10)")
    parser.add_argument("--headed", action="store_true",
                        help="以有头模式启动浏览器 (默认无头模式)")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
