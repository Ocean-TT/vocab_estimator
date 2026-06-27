"""
与 testyourvocab.com 对比实验

流程：
1. 用 Playwright 打开 testyourvocab.com
2. 第一页：按比例随机勾选单词
3. 点击 Continue
4. 第二页：同样按比例随机勾选
5. 抓取 testyourvocab.com 给出的词汇量结果 Ci
6. 同时把勾选的词传给我们的算法，得到结果 Di
7. 对比 Ci 和 Di 的差距

用法：
    python scripts/compare_testyourvocab.py --trials 20 --ratios 0.3 0.5 0.7
"""

import sys
import os
import random
import json
import csv
import argparse
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


URL = "https://testyourvocab.com/"
DEFAULT_TRIALS = 10
DEFAULT_RATIOS = [0.3, 0.5, 0.7]


@dataclass
class ComparisonResult:
    trial: int
    ratio: float
    known_count_round1: int
    total_count_round1: int
    known_count_round2: int
    total_count_round2: int
    tyv_result: int  # testyourvocab.com 给出的结果
    our_api_result: int  # 我们自己算法的结果（需要调用后端API）
    diff: int
    diff_pct: float


def extract_words_from_page(page) -> List[str]:
    """从当前页面提取所有单词（checkbox 对应的 label 文本）"""
    words = []
    # testyourvocab.com 的单词是 label 内的文本
    labels = page.query_selector_all('label[for^="word-"]')
    for label in labels:
        text = label.inner_text().strip()
        if text and text.isalpha():
            words.append(text.lower())
    return words


def check_words_randomly(page, ratio: float) -> List[str]:
    """按比例随机勾选单词，返回勾选的词列表"""
    words = extract_words_from_page(page)
    if not words:
        return []

    n_check = max(1, int(len(words) * ratio))
    selected = random.sample(words, min(n_check, len(words)))

    for word in selected:
        # 找到对应的 checkbox 并勾选
        try:
            checkbox = page.query_selector(f'input[value="{word}"]')
            if checkbox:
                checkbox.check()
        except Exception:
            pass

    return selected


def get_tyv_result(page) -> int:
    """从结果页抓取 testyourvocab.com 给出的词汇量"""
    try:
        # 结果页通常有一个大数字显示词汇量
        # 尝试多种选择器
        selectors = [
            'h1 strong',
            '.result-number',
            '[class*="result"]',
            'h1',
        ]
        for sel in selectors:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                # 提取数字
                import re
                numbers = re.findall(r'[\d,]+', text)
                if numbers:
                    return int(numbers[0].replace(',', ''))
    except Exception:
        pass
    return -1


def run_single_trial(trial: int, ratio: float, headless: bool = True) -> Dict:
    """跑一次完整的对比实验"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(URL, timeout=60000)
            page.wait_for_load_state('domcontentloaded')

            # --- Round 1 ---
            known_round1 = check_words_randomly(page, ratio)
            total_round1 = len(extract_words_from_page(page))

            # 点击 Continue
            continue_btn = page.query_selector('button[type="submit"], input[type="submit"]')
            if not continue_btn:
                continue_btn = page.query_selector('button:has-text("Continue")')
            if continue_btn:
                continue_btn.click()
                page.wait_for_load_state('domcontentloaded')
            else:
                browser.close()
                return {"error": "找不到 Continue 按钮"}

            # --- Round 2 ---
            known_round2 = check_words_randomly(page, ratio)
            total_round2 = len(extract_words_from_page(page))

            # 点击提交/查看结果
            submit_btn = page.query_selector('button[type="submit"], input[type="submit"]')
            if not submit_btn:
                submit_btn = page.query_selector('button:has-text("Continue")')
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state('domcontentloaded')
            else:
                browser.close()
                return {"error": "找不到提交按钮"}

            # 等待结果页加载
            page.wait_for_timeout(3000)

            # 抓取结果
            tyv_result = get_tyv_result(page)

            browser.close()

            all_known = known_round1 + known_round2
            return {
                "trial": trial,
                "ratio": ratio,
                "known_round1": len(known_round1),
                "total_round1": total_round1,
                "known_round2": len(known_round2),
                "total_round2": total_round2,
                "tyv_result": tyv_result,
                "all_known_words": all_known,
            }

        except Exception as e:
            browser.close()
            return {"error": str(e)}


def call_our_api(known_words: List[str], api_base: str = "http://localhost:8000") -> int:
    """调用我们自己的批量估算 API"""
    import urllib.request
    answers = [{"word": w, "known": True} for w in known_words]
    data = json.dumps({"answers": answers}).encode()
    req = urllib.request.Request(
        f"{api_base}/api/batch/estimate-from-words",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        return result.get("point_estimate", -1)
    except Exception as e:
        print(f"  API 调用失败: {e}")
        return -1


def run_comparison(
    trials: int,
    ratios: List[float],
    headless: bool = True,
    api_base: str = "http://localhost:8000",
) -> List[Dict]:
    """运行对比实验"""
    results = []

    for ratio in ratios:
        print(f"\n比例 {ratio*100:.0f}% ({trials} 次实验):")
        for i in range(trials):
            print(f"  Trial {i+1}/{trials}...", end=" ")
            trial_result = run_single_trial(i, ratio, headless=headless)

            if "error" in trial_result:
                print(f"失败: {trial_result['error']}")
                continue

            tyv = trial_result["tyv_result"]
            known_words = trial_result["all_known_words"]
            our = call_our_api(known_words, api_base=api_base)

            diff = our - tyv if (our > 0 and tyv > 0) else None
            diff_pct = (diff / tyv * 100) if (diff is not None and tyv > 0) else None

            record = {
                "trial": i + 1,
                "ratio": ratio,
                "known_total": len(known_words),
                "tyv_result": tyv,
                "our_result": our,
                "diff": diff,
                "diff_pct": round(diff_pct, 2) if diff_pct is not None else None,
            }
            results.append(record)

            status = f"TYV={tyv}, Our={our}"
            if diff is not None:
                status += f", Diff={diff:+d} ({diff_pct:+.1f}%)"
            print(status)

    return results


def save_results(results: List[Dict], filepath: str):
    """保存结果到 CSV"""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w",