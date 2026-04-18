"""Dataset preparation and persistence helpers for analytics workflows."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.statistics.dao import StatisticsDAO

RISK_LABELS = ["Low", "Medium", "High"]


def _risk_from_charges_bmi(charges: pd.Series, bmi: pd.Series | None = None) -> pd.Series:
    """Assign Low/Medium/High risk from charges with BMI as a secondary signal."""
    numeric_charges = pd.Series(pd.to_numeric(charges, errors="coerce"), index=charges.index)
    if numeric_charges.isna().all():
        raise ValueError("Cannot derive risk_category: charges column has no numeric values")

    charge_rank = numeric_charges.fillna(numeric_charges.median()).rank(pct=True, method="average")
    label_score = charge_rank

    # Keep charges dominant while allowing BMI to influence class boundaries.
    if bmi is not None:
        numeric_bmi = pd.Series(pd.to_numeric(bmi, errors="coerce"), index=charges.index)
        if numeric_bmi.notna().any() and numeric_bmi.nunique(dropna=True) > 1:
            bmi_rank = numeric_bmi.fillna(numeric_bmi.median()).rank(pct=True, method="average")
            label_score = 0.8 * charge_rank + 0.2 * bmi_rank

    # Rank once to make bin edges deterministic, then split into Low/Medium/High.
    unique_score = label_score.rank(method="first")
    labels = pd.qcut(unique_score, q=3, labels=RISK_LABELS)
    return pd.Series(labels, index=label_score.index).astype(str)


def build_dataset(data_path: Path) -> pd.DataFrame:
    """Load and prepare the health-insurance dataset for persistence and training."""
    df = pd.read_csv(data_path)

    raw_originals = df[["charges", "children", "age", "bmi"]].copy()

    for col in df.select_dtypes(include=[np.number]).columns:
        df[col] = df[col].fillna(df[col].mean())

    for col in df.select_dtypes(exclude=[np.number]).columns:
        mode = df[col].mode()[0] if not df[col].mode().empty else None
        df[col] = df[col].fillna(mode)

    df["sex_encoded"] = df["sex"].map({"male": 1, "female": 0})
    df["smoker_encoded"] = df["smoker"].map({"yes": 1, "no": 0})

    region_dummies = pd.get_dummies(df["region"], prefix="region")
    df = pd.concat([df, region_dummies], axis=1)

    # Keep a stable feature set for model training even if categories are missing.
    for col in ["region_northeast", "region_northwest", "region_southeast", "region_southwest"]:
        if col not in df.columns:
            df[col] = 0

    # Keep originals as provided in the source dataset, including missing values.
    age_original = pd.to_numeric(raw_originals["age"], errors="coerce").round().astype("Int64")
    children_original = pd.to_numeric(raw_originals["children"], errors="coerce").round().astype("Int64")
    df["charges_original"] = raw_originals["charges"]
    df["children_original"] = children_original
    df["age_original"] = age_original
    df["bmi_original"] = raw_originals["bmi"]

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    numeric_cols = [
        col
        for col in numeric_cols
        if col not in ["charges_original", "children_original", "age_original", "bmi_original"]
    ]

    for col in numeric_cols:
        min_val = df[col].min()
        max_val = df[col].max()
        if np.isclose(float(max_val), float(min_val)):
            df[col] = 0.0
        else:
            df[col] = (df[col] - min_val) / (max_val - min_val)

    df["risk_category"] = _risk_from_charges_bmi(df["charges_original"], df["bmi_original"])
    return df


def persist_dataset(df: pd.DataFrame) -> None:
    """Persist processed dataset to database via StatisticsDAO."""
    dao = StatisticsDAO()
    dao.persist_dataset(df)

