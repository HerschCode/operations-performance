"""
The actual scheduled job src/ml/retrain_trigger.py's docstring named as the missing
piece: "No scheduler is actually wired up in this environment." Wired now via
.github/workflows/retrain-check.yml's cron trigger -- this script is what that
workflow runs.

Fetches the REAL current case count from the live database (not hardcoded, unlike
retrain_trigger.py's own __main__ illustrative block), calls the existing decision
logic unchanged, and retrains for real if warranted. Exits non-zero on an actual
retrain (not on "no retrain needed" -- that's the expected, common outcome, not a
failure) so a human glancing at Action run history can tell "did anything happen"
from the green/red status without opening logs, while still logging plainly either
way.
"""
import sys

from dotenv import load_dotenv
from sqlalchemy import text

from src.api.db import get_engine, load_cases
from src.ml.retrain_trigger import check_retrain_needed
from src.ml.features import build_features
from src.ml.train import train_models, save_best_model
from src.analytics.sla_analysis import load_sla_targets, evaluate_sla
from src.observability.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("retrain_trigger")


def get_current_case_count() -> int:
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM analytics.process_cases")).scalar()


def main() -> int:
    load_dotenv()
    case_count = get_current_case_count()
    logger.info("Checking retrain need", extra={"current_case_count": case_count})

    result = check_retrain_needed(current_case_count=case_count)

    if not result.should_retrain:
        logger.info(
            "No retraining needed",
            extra={"days_since_training": result.days_since_training, "data_growth_pct": result.data_growth_pct},
        )
        print("No retraining needed yet.")
        return 0

    logger.info("Retraining triggered", extra={"reasons": result.reasons})
    print("Retraining triggered:")
    for reason in result.reasons:
        print(f"  - {reason}")

    cases = load_cases()
    evaluated = evaluate_sla(cases, load_sla_targets())
    X, y = build_features(evaluated)
    train_results = train_models(X, y, evaluated)
    save_best_model(train_results)

    logger.info("Retraining complete")
    print(f"Retrained and saved new model (case_count={case_count}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
