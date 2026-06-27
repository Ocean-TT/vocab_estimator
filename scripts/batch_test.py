"""
词汇量估计算法 — 后台批处理测试方法

通用的稳定性验证框架：
- 支持配置不同词汇量水平、不同测试长度、不同实验次数
- 输出平均值、标准差、相对误差、置信区间覆盖率
- 支持命令行参数调用
- 支持结果导出 CSV/JSON

用法示例：
    # 默认 900 次实验（3 种水平 × 3种长度 × 100次）
    python scripts/batch_test.py

    # 自定义参数
    python scripts/batch_test.py --vocabs 2000 5000 8000 --lengths 150 250 --trials 200

    # 只跑 1000 次实验，更精确
    python scripts/batch_test.py --trials 1000 --output output/batch_results.csv
"""

import sys
import os
import random
import math
import statistics
import argparse
import json
import csv
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config import LEVEL_RANGES, CONFIDENCE_Z
from backend.services.estimator import estimate_from_level_responses


DEFAULT_VOCAB_LEVELS = [3000, 6000, 12000]
DEFAULT_TEST_LENGTHS = [100, 200, 300]
DEFAULT_TRIALS = 100
TRANSITION_WIDTH = 500


def get_questions_per_level(total_questions: int) -> Dict[int, int]:
    """根据总题数，计算每层题数（平均分配到 5 层）"""
    per_level = total_questions // 5
    remainder = total_questions % 5
    result = {}
    for level in range(1, 6):
        result[level] = per_level + (1 if level <= remainder else 0)
    return result


def simulate_student_responses(
    true_vocab: int,
    num_per_level: Dict[int, int],
    transition_width: int = TRANSITION_WIDTH,
) -> Dict[str, Dict[int, int]]:
    """
    模拟学生答题。
    
    学生模型：
    - rank <= true_vocab - transition_width：100% 认识
    - true_vocab - transition_width < rank < true_vocab + transition_width：过渡带，线性变化
    - rank >= true_vocab + transition_width：0% 认识
    """
    level_known = {}
    level_total = {}

    for level, start_rank, end_rank in LEVEL_RANGES:
        n = num_per_level.get(level, 0)
        if n == 0:
            level_known[level] = 0
            level_total[level] = 0
            continue

        level_size = end_rank - start_rank + 1
        sample_size = min(n, level_size)

        ranks = random.sample(range(start_rank, end_rank + 1), sample_size)
        known = 0
        for rank in ranks:
            if rank <= true_vocab - transition_width:
                p = 1.0
            elif rank >= true_vocab + transition_width:
                p = 0.0
            else:
                p = 0.5 - (rank - true_vocab) / (2 * transition_width)
            if random.random() < p:
                known += 1

        level_known[level] = known
        level_total[level] = sample_size

    return {"level_known": level_known, "level_total": level_total}


def run_single_estimate(
    true_vocab: int,
    test_length: int,
) -> Dict[str, int]:
    """跑一次估算，返回点估计和上下界"""
    num_per_level = get_questions_per_level(test_length)
    responses = simulate_student_responses(true_vocab, num_per_level)

    level_responses = {}
    for level in [1, 2, 3, 4, 5]:
        known = responses["level_known"].get(level, 0)
        total = responses["level_total"].get(level, 0)
        resp_list = ["know"] * known + ["unknown"] * (total - known)
        level_responses[level] = resp_list

    result = estimate_from_level_responses(level_responses)
    return {
        "point_estimate": result.point_estimate,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
    }


@dataclass
class BatchStats:
    """一组实验的统计结果"""
    true_vocab: int
    test_length: int
    trials: int
    mean_estimate: float
    std_dev: float
    relative_error_pct: float
    coverage_pct: float
    min_estimate: int
    max_estimate: int
    median_estimate: float


def run_batch_experiment(
    vocab_levels: List[int],
    test_lengths: List[int],
    trials: int,
    seed: int = 42,
    verbose: bool = True,
) -> Dict[str, BatchStats]:
    """
    运行批量实验。
    
    Args:
        vocab_levels: 真实词汇量水平列表
        test_lengths: 测试题数列表
        trials: 每种组合的实验次数
        seed: 随机种子
        verbose: 是否打印进度
    
    Returns:
        字典，key 为 "V={v}, N={n}"，value 为 BatchStats
    """
    random.seed(seed)
    results = {}

    for v in vocab_levels:
        for n in test_lengths:
            key = f"V={v}, N={n}"
            if verbose:
                print(f"\n  实验：V={v}, N={n}, trials={trials}")

            estimates = []
            cover_count = 0

            for t in range(trials):
                result = run_single_estimate(v, n)
                point = result["point_estimate"]
                lower = result["lower_bound"]
                upper = result["upper_bound"]
                estimates.append(point)

                if lower <= v <= upper:
                    cover_count += 1

            mean_est = statistics.mean(estimates)
            std_est = statistics.stdev(estimates) if len(estimates) > 1 else 0.0
            rel_error = (mean_est - v) / v * 100
            coverage = cover_count / trials * 100
            median_est = statistics.median(estimates)

            stats = BatchStats(
                true_vocab=v,
                test_length=n,
                trials=trials,
                mean_estimate=round(mean_est, 2),
                std_dev=round(std_est, 2),
                relative_error_pct=round(rel_error, 2),
                coverage_pct=round(coverage, 2),
                min_estimate=min(estimates),
                max_estimate=max(estimates),
                median_estimate=round(median_est, 2),
            )
            results[key] = stats

            if verbose:
                print(f"    平均: {round(mean_est)} (真值: {v}), 误差: {rel_error:+.2f}%")
                print(f"    标准差: {round(std_est)}, 覆盖率: {coverage:.1f}%")

    return results


def print_results_table(results: Dict[str, BatchStats]):
    """打印汇总表格"""
    print("\n" + "=" * 90)
    print("  批处理测试结果汇总（分层比例估计算法稳定性验证）")
    print("=" * 90)
    header = f"{'真实V':>8} {'题数':>6} {'实验次':>6} {'平均估':>8} {'误差%':>8} {'标准差':>8} {'覆盖率%':>8} {'中位数':>8} {'范围':>16}"
    print(header)
    print("-" * 90)

    for stats in results.values():
        line = (
            f"{stats.true_vocab:>8} "
            f"{stats.test_length:>6} "
            f"{stats.trials:>6} "
            f"{stats.mean_estimate:>8.0f} "
            f"{stats.relative_error_pct:>+7.2f}% "
            f"{stats.std_dev:>8.0f} "
            f"{stats.coverage_pct:>7.2f}% "
            f"{stats.median_estimate:>8.0f} "
            f"[{stats.min_estimate}-{stats.max_estimate}]"
        )
        print(line)

    print("=" * 90)
    total = sum(s.trials for s in results.values())
    print(f"  总实验次数: {total}")
    print()


def save_to_csv(results: Dict[str, BatchStats], filepath: str):
    """保存结果到 CSV"""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "真实词汇量", "测试题数", "实验次数", "平均估算值", "中位数",
            "相对误差%", "标准差", "置信区间覆盖率%",
            "最小估算", "最大估算"
        ])
        for s in results.values():
            writer.writerow([
                s.true_vocab, s.test_length, s.trials,
                s.mean_estimate, s.median_estimate,
                s.relative_error_pct, s.std_dev, s.coverage_pct,
                s.min_estimate, s.max_estimate,
            ])
    print(f"  CSV 已保存: {filepath}")


def save_to_json(results: Dict[str, BatchStats], filepath: str):
    """保存结果到 JSON"""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    data = {k: asdict(v) for k, v in results.items()}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  JSON 已保存: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="词汇量估计算法 - 后台批处理稳定性测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默认参数（900次实验）
  python scripts/batch_test.py

  # 自定义词汇量水平和测试长度
  python scripts/batch_test.py --vocabs 2000 4000 8000 --lengths 150 300

  # 更多实验次数，更精确
  python scripts/batch_test.py --trials 500

  # 指定输出文件
  python scripts/batch_test.py --output output/results.csv
        """,
    )
    parser.add_argument(
        "--vocabs",
        type=int,
        nargs="+",
        default=DEFAULT_VOCAB_LEVELS,
        help=f"真实词汇量水平列表（默认: {DEFAULT_VOCAB_LEVELS}",
    )
    parser.add_argument(
        "--lengths",
        type=int,
        nargs="+",
        default=DEFAULT_TEST_LENGTHS,
        help=f"测试题数列表（默认: {DEFAULT_TEST_LENGTHS}",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
        help=f"每种组合的实验次数（默认: {DEFAULT_TRIALS}）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（默认: 42）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 CSV 文件路径",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="输出 JSON 文件路径",
    )

    args = parser.parse_args()

    total_experiments = len(args.vocabs) * len(args.lengths) * args.trials

    print("=" * 70)
    print("  词汇量估计算法 - 后台批处理稳定性测试")
    print("=" * 70)
    print(f"  词汇量水平: {args.vocabs}")
    print(f"  测试长度:   {args.lengths}")
    print(f"  每组实验:   {args.trials} 次")
    print(f"  总实验数:   {total_experiments} 次")
    print("=" * 70)

    results = run_batch_experiment(
        vocab_levels=args.vocabs,
        test_lengths=args.lengths,
        trials=args.trials,
        seed=args.seed,
        verbose=True,
    )

    print_results_table(results)

    if args.output:
        save_to_csv(results, args.output)
    else:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        csv_path = os.path.join(output_dir, "batch_test_results.csv")
        save_to_csv(results, csv_path)

    if args.json:
        save_to_json(results, args.json)


if __name__ == "__main__":
    main()
