#!/usr/bin/env python3
"""
Sample Size Calculator for Clinical Trials

Calculates required sample sizes for clinical trials based on:
- Continuous endpoints (two-sample t-test)
- Binary endpoints (two-proportion test)

Usage:
    python sample_size_calculator.py --endpoint-type continuous --effect-size 0.5 --std-dev 1.0
    python sample_size_calculator.py --endpoint-type binary --p1 0.3 --p2 0.5 --output results.json
"""

import argparse
import json
import math
from datetime import datetime

try:
    from scipy.stats import norm

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Using basic calculations.")


def calculate_continuous_sample_size(
    effect_size: float, std_dev: float, alpha: float = 0.05, power: float = 0.80, allocation_ratio: float = 1.0
) -> dict:
    """
    Calculate sample size for continuous endpoint (two-sample t-test).

    Args:
        effect_size: Expected mean difference between groups
        std_dev: Expected standard deviation (pooled)
        alpha: Type I error rate (default 0.05)
        power: Statistical power (default 0.80)
        allocation_ratio: Ratio of treatment to control (default 1:1)

    Returns:
        Dictionary with sample size calculations
    """
    if SCIPY_AVAILABLE:
        z_alpha = norm.ppf(1 - alpha / 2)
        z_beta = norm.ppf(power)
    else:
        # Standard normal quantiles for common values
        z_table = {0.05: 1.96, 0.01: 2.576, 0.10: 1.645}
        power_table = {0.80: 0.842, 0.90: 1.282, 0.95: 1.645}
        z_alpha = z_table.get(alpha, 1.96)
        z_beta = power_table.get(power, 0.842)

    # Standardized effect size (Cohen's d)
    d = effect_size / std_dev

    # Sample size per arm (equal allocation)
    k = allocation_ratio
    n_per_arm = ((z_alpha + z_beta) ** 2 * (1 + 1 / k) * std_dev**2) / (effect_size**2)
    n_per_arm = math.ceil(n_per_arm)

    # Total sample size
    n_total = n_per_arm * (1 + k)

    return {
        "endpoint_type": "continuous",
        "effect_size": effect_size,
        "std_dev": std_dev,
        "cohens_d": round(d, 3),
        "alpha": alpha,
        "power": power,
        "allocation_ratio": f"{allocation_ratio}:1",
        "n_per_arm": n_per_arm,
        "n_control": n_per_arm,
        "n_treatment": math.ceil(n_per_arm * k),
        "n_total": math.ceil(n_total),
        "formula": "Two-sample t-test",
        "assumptions": ["Normal distribution of outcome", "Equal variances between groups", "Independent samples"],
    }


def calculate_binary_sample_size(
    p1: float, p2: float, alpha: float = 0.05, power: float = 0.80, allocation_ratio: float = 1.0
) -> dict:
    """
    Calculate sample size for binary endpoint (two-proportion test).

    Args:
        p1: Expected proportion in control group
        p2: Expected proportion in treatment group
        alpha: Type I error rate (default 0.05)
        power: Statistical power (default 0.80)
        allocation_ratio: Ratio of treatment to control (default 1:1)

    Returns:
        Dictionary with sample size calculations
    """
    if SCIPY_AVAILABLE:
        z_alpha = norm.ppf(1 - alpha / 2)
        z_beta = norm.ppf(power)
    else:
        z_table = {0.05: 1.96, 0.01: 2.576, 0.10: 1.645}
        power_table = {0.80: 0.842, 0.90: 1.282, 0.95: 1.645}
        z_alpha = z_table.get(alpha, 1.96)
        z_beta = power_table.get(power, 0.842)

    # Effect size (absolute risk difference)
    effect = abs(p2 - p1)

    # Pooled proportion
    p_bar = (p1 + p2) / 2

    # Sample size per arm (Fleiss formula)
    k = allocation_ratio
    numerator = (
        z_alpha * math.sqrt(p_bar * (1 - p_bar) * (1 + 1 / k)) + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / k)
    ) ** 2
    denominator = (p2 - p1) ** 2

    n_per_arm = numerator / denominator
    n_per_arm = math.ceil(n_per_arm)

    # Total sample size
    n_total = n_per_arm * (1 + k)

    # Odds ratio and relative risk
    odds_ratio = (p2 / (1 - p2)) / (p1 / (1 - p1))
    relative_risk = p2 / p1

    return {
        "endpoint_type": "binary",
        "p_control": p1,
        "p_treatment": p2,
        "absolute_difference": round(effect, 3),
        "relative_risk": round(relative_risk, 3),
        "odds_ratio": round(odds_ratio, 3),
        "alpha": alpha,
        "power": power,
        "allocation_ratio": f"{allocation_ratio}:1",
        "n_per_arm": n_per_arm,
        "n_control": n_per_arm,
        "n_treatment": math.ceil(n_per_arm * k),
        "n_total": math.ceil(n_total),
        "formula": "Two-proportion test (Fleiss)",
        "assumptions": ["Independent samples", "Binary outcome", "Large sample approximation"],
    }


def adjust_for_dropout(n_total: int, dropout_rate: float) -> dict:
    """
    Adjust sample size for expected dropout/attrition.

    Args:
        n_total: Calculated sample size
        dropout_rate: Expected dropout rate (0-1)

    Returns:
        Dictionary with adjusted sample size
    """
    adjusted_n = math.ceil(n_total / (1 - dropout_rate))

    return {
        "original_n": n_total,
        "dropout_rate": dropout_rate,
        "dropout_rate_percent": f"{dropout_rate * 100:.0f}%",
        "adjusted_n_total": adjusted_n,
        "additional_subjects": adjusted_n - n_total,
    }


def format_results(calculation: dict, dropout_adjustment: dict) -> dict:
    """
    Format complete sample size results.
    """
    return {
        "calculation_date": datetime.now().isoformat(),
        "calculator_version": "1.0.0",
        "scipy_available": SCIPY_AVAILABLE,
        "primary_calculation": calculation,
        "dropout_adjustment": dropout_adjustment,
        "final_recommendation": {
            "n_per_arm": math.ceil(dropout_adjustment["adjusted_n_total"] / 2),
            "n_total": dropout_adjustment["adjusted_n_total"],
            "enrollment_target": dropout_adjustment["adjusted_n_total"],
        },
        "notes": [
            "Sample size calculated using standard statistical formulas",
            f"Adjusted for {dropout_adjustment['dropout_rate_percent']} expected dropout",
            "Recommend validation by qualified biostatistician",
            "Consider stratification factors which may require adjustment",
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Calculate sample size for clinical trials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Continuous endpoint:
    python sample_size_calculator.py --endpoint-type continuous --effect-size 5 --std-dev 10

  Binary endpoint:
    python sample_size_calculator.py --endpoint-type binary --p1 0.3 --p2 0.5

  With custom parameters:
    python sample_size_calculator.py --endpoint-type continuous --effect-size 0.5 \\
        --std-dev 1.0 --alpha 0.05 --power 0.90 --dropout 0.20 --output results.json
        """,
    )

    parser.add_argument(
        "--endpoint-type", type=str, required=True, choices=["continuous", "binary"], help="Type of primary endpoint"
    )

    # Continuous endpoint parameters
    parser.add_argument("--effect-size", type=float, help="Expected mean difference (for continuous endpoints)")
    parser.add_argument("--std-dev", type=float, help="Standard deviation (for continuous endpoints)")

    # Binary endpoint parameters
    parser.add_argument("--p1", type=float, help="Expected proportion in control group (for binary endpoints)")
    parser.add_argument("--p2", type=float, help="Expected proportion in treatment group (for binary endpoints)")

    # Common parameters
    parser.add_argument("--alpha", type=float, default=0.05, help="Type I error rate (default: 0.05)")
    parser.add_argument("--power", type=float, default=0.80, help="Statistical power (default: 0.80)")
    parser.add_argument("--dropout", type=float, default=0.15, help="Expected dropout rate (default: 0.15)")
    parser.add_argument(
        "--allocation", type=float, default=1.0, help="Allocation ratio treatment:control (default: 1.0 for 1:1)"
    )
    parser.add_argument("--output", type=str, help="Output file path for JSON results")

    args = parser.parse_args()

    # Validate parameters
    if args.endpoint_type == "continuous":
        if args.effect_size is None or args.std_dev is None:
            parser.error("Continuous endpoint requires --effect-size and --std-dev")
        calculation = calculate_continuous_sample_size(
            effect_size=args.effect_size,
            std_dev=args.std_dev,
            alpha=args.alpha,
            power=args.power,
            allocation_ratio=args.allocation,
        )
    else:  # binary
        if args.p1 is None or args.p2 is None:
            parser.error("Binary endpoint requires --p1 and --p2")
        calculation = calculate_binary_sample_size(
            p1=args.p1, p2=args.p2, alpha=args.alpha, power=args.power, allocation_ratio=args.allocation
        )

    # Adjust for dropout
    dropout_adj = adjust_for_dropout(calculation["n_total"], args.dropout)

    # Format results
    results = format_results(calculation, dropout_adj)

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {args.output}")

    # Display summary
    print("\n" + "=" * 60)
    print("SAMPLE SIZE CALCULATION RESULTS")
    print("=" * 60)
    print(f"\nEndpoint Type: {args.endpoint_type.capitalize()}")

    if args.endpoint_type == "continuous":
        print(f"Effect Size: {args.effect_size}")
        print(f"Standard Deviation: {args.std_dev}")
        print(f"Cohen's d: {calculation['cohens_d']}")
    else:
        print(f"Control Proportion: {args.p1}")
        print(f"Treatment Proportion: {args.p2}")
        print(f"Absolute Difference: {calculation['absolute_difference']}")
        print(f"Odds Ratio: {calculation['odds_ratio']}")

    print(f"\nAlpha: {args.alpha}")
    print(f"Power: {args.power * 100:.0f}%")
    print(f"Allocation: {calculation['allocation_ratio']}")

    print("\n--- Calculated Sample Size ---")
    print(f"N per arm: {calculation['n_per_arm']}")
    print(f"Total N (unadjusted): {calculation['n_total']}")

    print("\n--- Dropout Adjustment ---")
    print(f"Expected dropout: {args.dropout * 100:.0f}%")
    print(f"Total N (adjusted): {dropout_adj['adjusted_n_total']}")

    print("\n--- RECOMMENDATION ---")
    print(f"Enrollment Target: {results['final_recommendation']['enrollment_target']} subjects")
    print(f"Per Arm: {results['final_recommendation']['n_per_arm']} subjects")

    print("\n" + "=" * 60)
    print("⚠️  Validation by qualified biostatistician recommended")
    print("=" * 60 + "\n")

    return results


if __name__ == "__main__":
    main()
