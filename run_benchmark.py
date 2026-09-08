"""
Quantitative Benchmark Runner for Fact Knowledge Layer (FKL).
Runs test cases, evaluates faithfulness, contradiction preservation, and prints executive scorecard.

Usage:
    python run_benchmark.py
"""

import sys
from pathlib import Path

# Ensure backend can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from backend.benchmarks.evaluator import FactBenchmarkEvaluator


def main():
    print("=" * 80)
    print(" 🧪 FACT KNOWLEDGE LAYER — QUANTITATIVE BENCHMARK EVALUATION")
    print(" Measuring Faithfulness, Contradiction Recall, Hallucination Rejection & Latency")
    print("=" * 80)

    evaluator = FactBenchmarkEvaluator()
    print("\nRunning test matrix...")
    results = evaluator.run_evaluations()

    summary = results["summary"]

    print("\n" + "-" * 80)
    print(f" 🏆 OVERALL SYSTEM GRADE: [{summary['overall_grade']}]")
    print("-" * 80)
    print(f"  • Grounded Faithfulness Score:     {summary['faithfulness_score']}%  (Target: 100%)")
    print(f"  • Contradiction Recall:            {summary['contradiction_recall']}%  (Target: 100%)")
    print(f"  • Context Reconciliation Accuracy: {summary['reconciliation_accuracy']}%  (Target: 100%)")
    print(f"  • Uncertainty Calibration Rate:    {summary['uncertainty_calibration']}%  (Target: 100%)")
    print(f"  • Zero-Hallucination Guarantee:    {summary['zero_hallucination_rate']}%")
    print(f"  • Average Retrieval/RAG Latency:   {summary['avg_latency_ms']} ms")
    print(f"  • Test Cases Passed:               {summary['passed_cases']}/{summary['total_cases_evaluated']}")
    print("-" * 80)

    print("\n📋 DETAILED BENCHMARK TEST MATRIX:")
    for c in results["cases"]:
        status = "✅ PASS" if c["passed"] else "❌ FAIL"
        print(f"\n  [{c['case_id']}] {status} | Category: {c['category']}")
        print(f"      Query:      \"{c['query']}\"")
        print(f"      Confidence: [{c['confidence']}] | Validator: [{c['validation_status']}] | Latency: {c['latency_ms']}ms")
        print(f"      Audit:      {c['details']}")

    print("\n" + "=" * 80)
    print(" ✅ BENCHMARK EVALUATION COMPLETE.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
