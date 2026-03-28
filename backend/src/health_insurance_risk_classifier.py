#!/usr/bin/env python3
"""Script version of the health insurance risk classifier workflow.
- load CSV
- clean data
- encode categories
- normalize numeric features (while preserving originals)
- apply charges-based risk classification
- persist results to Azure SQL (via StatisticsRepository and TrainingRepository)
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from tensorflow import keras
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.utils import to_categorical

from src.statistics.dao import StatisticsDAO
from src.storage.dao import StorageDAO
from src.training.dao import TrainingDAO

RISK_LABELS = ["Low", "Medium", "High"]
MODEL_BLOB_NAME = "models/risk_model.keras"
MODEL_REGISTRY_BLOB_NAME = "models/model_registry.json"
PLOTS_BLOB_PREFIX = "plots"

logger = logging.getLogger(__name__)


def _ordered_risk_crosstab(series: pd.Series, risk_series: pd.Series) -> pd.DataFrame:
    """Return a crosstab with stable Low/Medium/High columns, even when some are missing."""
    return pd.crosstab(series, risk_series).reindex(columns=RISK_LABELS, fill_value=0)


def _default_model_path() -> Path:
    return Path(tempfile.gettempdir()) / "wsaa-model-cache" / MODEL_BLOB_NAME


def _read_registry_payload(storage: StorageDAO) -> dict[str, object] | None:
    if not storage.exists(MODEL_REGISTRY_BLOB_NAME):
        return None

    payload_bytes = storage.download_bytes(MODEL_REGISTRY_BLOB_NAME)
    return json.loads(payload_bytes.decode("utf-8"))


def _versioned_model_path(base_model_path: Path, model_version: str) -> Path:
    return base_model_path.with_name(f"{base_model_path.stem}_{model_version}{base_model_path.suffix}")


def _versioned_model_blob_name(versioned_model_path: Path) -> str:
    return f"models/{versioned_model_path.name}"


def _extract_version_number(model_version: str) -> int | None:
    match = re.fullmatch(r"nn-v(\d+)", model_version)
    if match is None:
        return None
    return int(match.group(1))


def _next_nn_model_version(storage: StorageDAO) -> str:
    payload = _read_registry_payload(storage)
    if payload is None:
        return "nn-v1"

    current_version = str(payload.get("active_model_version") or "")
    current_number = _extract_version_number(current_version)
    if current_number is None:
        raise ValueError("Invalid active_model_version in model registry")
    return f"nn-v{current_number + 1}"


def _write_active_model_registry(storage: StorageDAO, model_version: str, model_blob_name: str) -> None:
    payload = json.dumps(
        {
            "active_model_version": model_version,
            "active_model_path": model_blob_name,
        }
    )
    storage.upload_stream(io.BytesIO(payload.encode("utf-8")), MODEL_REGISTRY_BLOB_NAME, overwrite=True)


def _download_model_blob(storage: StorageDAO, blob_name: str, destination_dir: Path) -> Path:
    if not storage.exists(blob_name):
        raise FileNotFoundError(f"Model blob not found: {blob_name}")

    destination = destination_dir / Path(blob_name).name
    storage.download_file(blob_name, destination)
    return destination


def _normalize_model_blob_name(blob_name: str) -> str:
    normalized = blob_name.strip()
    if not normalized:
        raise ValueError("Invalid model registry payload")
    if "/" not in normalized:
        return f"models/{normalized}"
    return normalized


def _upload_current_figure(storage: StorageDAO, filename: str) -> None:
    buffer = io.BytesIO()
    plt.savefig(buffer, dpi=100, bbox_inches="tight")
    buffer.seek(0)
    storage.upload_stream(buffer, blob_name=f"{PLOTS_BLOB_PREFIX}/{filename}", overwrite=True)


def get_active_nn_model_info(base_model_path: Path | None = None) -> tuple[str | None, Path | None]:
    resolved_base_path = base_model_path or _default_model_path()
    storage = StorageDAO()
    payload = _read_registry_payload(storage)

    if resolved_base_path.exists():
        if payload is None:
            return "nn-v1", resolved_base_path
        model_version = str(payload.get("active_model_version") or "")
        if not model_version:
            raise ValueError("Invalid model registry payload")
        return model_version, resolved_base_path

    temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-active-model-"))
    if payload is None:
        if not storage.exists(MODEL_BLOB_NAME):
            return None, None
        return "nn-v1", _download_model_blob(storage, MODEL_BLOB_NAME, temp_dir)

    model_version = str(payload.get("active_model_version") or "")
    model_path_raw = payload.get("active_model_path")
    if not model_version or not model_path_raw:
        raise ValueError("Invalid model registry payload")

    active_blob_name = _normalize_model_blob_name(str(model_path_raw))
    return model_version, _download_model_blob(storage, active_blob_name, temp_dir)


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


def evaluate_risk_from_nn_raw_features(
    age: int,
    bmi: float,
    children: int,
    smoker: str,
    sex: str,
    region: str,
    data_path: Path,
    model_path: Path,
) -> str:
    """Evaluate one applicant with the trained neural network model."""

    bmi_value = float(bmi)
    if bmi_value < 10.0 or bmi_value > 70.0:
        return "High"

    reference = pd.read_csv(data_path, usecols=["age", "bmi", "children"])
    for col in reference.columns:
        reference[col] = reference[col].fillna(reference[col].mean())

    def _normalize(value: float, series: pd.Series) -> float:
        min_val = float(series.min())
        max_val = float(series.max())
        if np.isclose(max_val, min_val):
            return 0.0
        norm = (float(value) - min_val) / (max_val - min_val)
        return float(np.clip(norm, 0.0, 1.0))

    sex_normalized = str(sex).lower()
    smoker_normalized = str(smoker).lower()
    region_normalized = str(region).lower()

    features = {
        "age": _normalize(age, reference["age"]),
        "bmi": _normalize(bmi, reference["bmi"]),
        "children": _normalize(children, reference["children"]),
        "sex_encoded": 1.0 if sex_normalized == "male" else 0.0,
        "smoker_encoded": 1.0 if smoker_normalized == "yes" else 0.0,
        "region_northeast": 1.0 if region_normalized == "northeast" else 0.0,
        "region_northwest": 1.0 if region_normalized == "northwest" else 0.0,
        "region_southeast": 1.0 if region_normalized == "southeast" else 0.0,
        "region_southwest": 1.0 if region_normalized == "southwest" else 0.0,
    }
    input_array = np.array(
        [
            [
                features["age"],
                features["bmi"],
                features["children"],
                features["sex_encoded"],
                features["smoker_encoded"],
                features["region_northeast"],
                features["region_northwest"],
                features["region_southeast"],
                features["region_southwest"],
            ]
        ],
        dtype=float,
    )

    model = keras.models.load_model(model_path)
    probabilities = model.predict(input_array, verbose=0)
    predicted_index = int(np.argmax(probabilities[0]))
    if predicted_index < 0 or predicted_index >= len(RISK_LABELS):
        raise ValueError("Invalid model prediction index")
    return RISK_LABELS[predicted_index]


def evaluate_risk_with_best_model(
    age: int,
    bmi: float,
    children: int,
    smoker: str,
    sex: str,
    region: str,
    data_path: Path,
    model_path: Path | None = None,
) -> tuple[str, str]:
    """Use the active NN model only; raise if no active model is available."""
    resolved_model_path = model_path or _default_model_path()
    active_model_version, active_model_path = get_active_nn_model_info(resolved_model_path)

    if active_model_path is None or active_model_version is None:
        raise ValueError("Active model not available")

    risk_label = evaluate_risk_from_nn_raw_features(
        age=age,
        bmi=bmi,
        children=children,
        smoker=smoker,
        sex=sex,
        region=region,
        data_path=data_path,
        model_path=active_model_path,
    )
    return risk_label, active_model_version


def build_dataset(data_path: Path) -> pd.DataFrame:
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
    children_original = (
        pd.to_numeric(raw_originals["children"], errors="coerce").round().astype("Int64")
    )
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
    """Persist processed dataset to database via StatisticsRepository."""
    dao = StatisticsDAO()
    dao.persist_dataset(df)



def run_sql_checks() -> None:
    """Execute diagnostic SQL checks via StatisticsRepository."""
    dao = StatisticsDAO()
    results = dao.run_sql_checks()
    
    print("Query 1 - Total records:")
    print(f"  Total: {results['total_records']}")
    print()

    print("Query 2 - Risk category distribution:")
    for item in results["risk_distribution"]:
        print(f"  {item['risk_category']}: {item['count']}")
    print()

    print("Query 3 - Average age and BMI by risk category:")
    for item in results["stats_by_risk"]:
        print(f"  {item['risk_category']}: avg_age={item['avg_age']:.2f}, avg_bmi={item['avg_bmi']:.2f}, count={item['count']}")
    print()


def load_analysis_data() -> pd.DataFrame:
    """Load analysis data via StatisticsRepository."""
    dao = StatisticsDAO()
    return dao.load_analysis_data()


def _plot_crosstab_or_placeholder(
    table: pd.DataFrame,
    ax: plt.Axes,
    *,
    colors: list[str],
    empty_message: str = "No data available",
) -> None:
    """Plot crosstab as a bar chart, or draw a placeholder when the table has no rows."""
    if table.empty:
        ax.text(0.5, 0.5, empty_message, ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        return
    table.plot(kind="bar", ax=ax, color=colors)


def run_eda(df_analysis: pd.DataFrame, plot_dir: Path) -> None:
    _ = plot_dir
    storage = StorageDAO()
    plt.style.use("default")
    sns.set_palette("husl")

    if df_analysis.empty:
        logger.warning("EDA received empty analysis dataframe; generating placeholder plots where needed")

    risk_order = RISK_LABELS
    risk_colors = ["green", "orange", "red"]

    # 01 Age
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(df_analysis["age"], bins=30, color="skyblue", edgecolor="black", alpha=0.7)
    axes[0].set_title("Distribution of Age (Normalized)")
    axes[0].set_xlabel("Age (Normalized)")
    axes[0].set_ylabel("Count")
    sns.boxplot(data=df_analysis, x="risk_category", y="age", ax=axes[1], order=risk_order)
    axes[1].set_title("Age Distribution by Risk Category")
    axes[1].set_xlabel("Risk Category")
    axes[1].set_ylabel("Age (Normalized)")
    plt.tight_layout()
    _upload_current_figure(storage, "01_age_distribution.png")
    plt.close()

    # 02 BMI
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(df_analysis["bmi"], bins=30, color="skyblue", edgecolor="black", alpha=0.7)
    axes[0].set_title("Distribution of BMI (Normalized)")
    axes[0].set_xlabel("BMI (Normalized)")
    axes[0].set_ylabel("Count")
    sns.boxplot(data=df_analysis, x="risk_category", y="bmi", ax=axes[1], order=risk_order)
    axes[1].set_title("BMI Distribution by Risk Category")
    axes[1].set_xlabel("Risk Category")
    axes[1].set_ylabel("BMI (Normalized)")
    plt.tight_layout()
    _upload_current_figure(storage, "02_bmi_distribution.png")
    plt.close()

    # 03 Charges
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(
        df_analysis["charges_original"], bins=30, color="skyblue", edgecolor="black", alpha=0.7
    )
    axes[0].set_title("Distribution of Insurance Charges")
    axes[0].set_xlabel("Insurance Charges (USD)")
    axes[0].set_ylabel("Count")
    sns.boxplot(data=df_analysis, x="risk_category", y="charges_original", ax=axes[1], order=risk_order)
    axes[1].set_title("Medical Charges by Risk Category")
    axes[1].set_xlabel("Risk Category")
    axes[1].set_ylabel("Insurance Charges")
    plt.tight_layout()
    _upload_current_figure(storage, "03_charges_distribution.png")
    plt.close()

    # 04 Smoker
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    smoker_counts = df_analysis["smoker"].value_counts()
    axes[0].bar(smoker_counts.index, smoker_counts.values, color=["lightblue", "salmon"])
    axes[0].set_title("Distribution of Smoker Status")
    axes[0].set_xlabel("Smoker Status")
    axes[0].set_ylabel("Count")
    smoker_risk = _ordered_risk_crosstab(df_analysis["smoker"], df_analysis["risk_category"])
    _plot_crosstab_or_placeholder(smoker_risk, axes[1], colors=risk_colors)
    axes[1].set_title("Risk Category by Smoker Status")
    axes[1].set_xlabel("Smoker Status")
    axes[1].set_ylabel("Count")
    plt.tight_layout()
    _upload_current_figure(storage, "04_smoker_analysis.png")
    plt.close()

    # 05 Sex
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sex_counts = df_analysis["sex"].value_counts()
    axes[0].bar(sex_counts.index, sex_counts.values, color=["lightblue", "pink"])
    axes[0].set_title("Distribution of Sex")
    axes[0].set_xlabel("Sex")
    axes[0].set_ylabel("Count")
    sex_risk = _ordered_risk_crosstab(df_analysis["sex"], df_analysis["risk_category"])
    _plot_crosstab_or_placeholder(sex_risk, axes[1], colors=risk_colors)
    axes[1].set_title("Risk Category by Sex")
    axes[1].set_xlabel("Sex")
    axes[1].set_ylabel("Count")
    plt.tight_layout()
    _upload_current_figure(storage, "05_sex_analysis.png")
    plt.close()

    # 06 Children
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    children_counts = df_analysis["children_original"].value_counts().sort_index()
    x_positions = range(len(children_counts))
    axes[0].bar(x_positions, children_counts.values, color="skyblue", edgecolor="black", alpha=0.7)
    axes[0].set_title("Distribution of Number of Children")
    axes[0].set_xticks(list(x_positions))
    axes[0].set_xticklabels([str(int(v)) for v in children_counts.index])
    axes[0].set_xlabel("Number of Children")
    axes[0].set_ylabel("Count")
    children_risk = _ordered_risk_crosstab(df_analysis["children_original"], df_analysis["risk_category"])
    _plot_crosstab_or_placeholder(children_risk, axes[1], colors=risk_colors)
    axes[1].set_title("Risk Category by Number of Children")
    axes[1].set_xlabel("Number of Children")
    axes[1].set_ylabel("Count")
    plt.tight_layout()
    _upload_current_figure(storage, "06_children_analysis.png")
    plt.close()

    # 07 Risk distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    risk_counts = df_analysis["risk_category"].value_counts().reindex(risk_order, fill_value=0)
    axes[0].bar(risk_counts.index, risk_counts.values, color=risk_colors)
    axes[0].set_title("Distribution of Risk Categories")
    axes[0].set_xlabel("Risk Category")
    axes[0].set_ylabel("Count")
    if int(risk_counts.sum()) > 0:
        axes[1].pie(risk_counts.values, labels=risk_counts.index, autopct="%1.1f%%", colors=risk_colors)
    else:
        axes[1].text(0.5, 0.5, "No risk data", ha="center", va="center")
        axes[1].axis("off")
    axes[1].set_title("Risk Category Proportions")
    plt.tight_layout()
    _upload_current_figure(storage, "07_risk_category_distribution.png")
    plt.close()

    # 08 Correlation
    numeric_features = ["age", "bmi", "children", "sex_encoded", "smoker_encoded", "charges_original"]
    correlation_matrix = df_analysis[numeric_features].copy().corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(correlation_matrix, annot=True, cmap="coolwarm", center=0, fmt=".3f", ax=ax)
    ax.set_title("Correlation Matrix of Health Insurance Features")
    ax.set_xlabel("Features")
    ax.set_ylabel("Features")
    plt.tight_layout()
    _upload_current_figure(storage, "08_correlation_matrix.png")
    plt.close()

    print("EDA completed. Plots uploaded to Azure Blob storage.")


def run_training(plot_dir: Path, epochs: int) -> tuple[str, str]:
    logger.info("Starting training run (epochs=%s, plot_dir=%s)", epochs, plot_dir)
    # Load training data via DAO
    dao = TrainingDAO()
    df_model_data = dao.load_training_data()

    feature_cols = [
        "age",
        "bmi",
        "children",
        "sex_encoded",
        "smoker_encoded",
        "region_northeast",
        "region_northwest",
        "region_southeast",
        "region_southwest",
    ]
    # SQL drivers may return object-like values (e.g., Decimal); force numeric tensors for Keras.
    X_features = df_model_data[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X_features = X_features.astype(np.float32)

    y_encoded_labels = (
        df_model_data["risk_category"].astype(str).str.strip().map({"Low": 0, "Medium": 1, "High": 2})
    )
    if y_encoded_labels.isna().any():
        invalid_labels = sorted(df_model_data.loc[y_encoded_labels.isna(), "risk_category"].astype(str).unique())
        raise ValueError(f"Unexpected risk_category labels in training data: {invalid_labels}")
    y_encoded_labels = y_encoded_labels.astype(np.int64)

    X_train, X_test, y_train, y_test = train_test_split(
        X_features, y_encoded_labels, test_size=0.2, random_state=42
    )

    X_train_array = X_train.to_numpy(dtype=np.float32)
    X_test_array = X_test.to_numpy(dtype=np.float32)
    y_train_categorical = to_categorical(y_train.to_numpy(dtype=np.int64), num_classes=3)

    model = Sequential(
        [
            keras.layers.Input(shape=(9,)),
            Dense(16, activation="relu"),
            Dropout(0.3),
            Dense(3, activation="softmax"),
        ]
    )
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.01),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    early_stopping = EarlyStopping(monitor="val_loss", patience=50, restore_best_weights=True)
    history = model.fit(
        X_train_array,
        y_train_categorical,
        epochs=epochs,
        batch_size=32,
        validation_split=0.2,
        callbacks=[early_stopping],
        verbose=0,
    )

    y_pred_probs = model.predict(X_test_array, verbose=0)
    y_pred = np.argmax(y_pred_probs, axis=1)
    risk_order = ["Low", "Medium", "High"]

    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, labels=[0, 1, 2])
    report_text = classification_report(
        y_test,
        y_pred,
        labels=[0, 1, 2],
        target_names=risk_order,
        zero_division=0,
    )
    print(f"Training completed at epoch {len(history.history['accuracy'])}")
    print(report_text)

    _ = plot_dir
    storage = StorageDAO()

    # 10 Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])
    row_sums = cm.sum(axis=1, keepdims=True)
    cm_normalized = np.divide(cm.astype(float), row_sums, out=np.zeros_like(cm, dtype=float), where=row_sums != 0)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=risk_order, yticklabels=risk_order, ax=axes[0])
    axes[0].set_title("Confusion Matrix (Counts)")
    axes[0].set_xlabel("Predicted Label")
    axes[0].set_ylabel("True Label")
    sns.heatmap(cm_normalized, annot=True, fmt=".1%", cmap="Blues", xticklabels=risk_order, yticklabels=risk_order, ax=axes[1], vmin=0, vmax=1)
    axes[1].set_title("Confusion Matrix (Percentages)")
    axes[1].set_xlabel("Predicted Label")
    axes[1].set_ylabel("True Label")
    plt.tight_layout()
    _upload_current_figure(storage, "10_confusion_matrix.png")
    plt.close()

    # 11 Per-risk metrics
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    metric_items = [("Precision", precision), ("Recall", recall), ("F1-Score", f1)]
    for idx, (metric_name, metric_values) in enumerate(metric_items):
        axes[idx].bar(risk_order, metric_values, color=["green", "orange", "red"], edgecolor="black", alpha=0.7)
        axes[idx].set_title(f"{metric_name} by Risk")
        axes[idx].set_ylim([0, 1.1])
        axes[idx].set_xlabel("Risk Category")
        axes[idx].set_ylabel(metric_name)
    plt.tight_layout()
    _upload_current_figure(storage, "11_per_risk_performance.png")
    plt.close()

    resolved_model_path = _default_model_path()

    model_version = _next_nn_model_version(storage)
    versioned_model_path = _versioned_model_path(resolved_model_path, model_version)
    versioned_model_blob_name = _versioned_model_blob_name(versioned_model_path)

    resolved_model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(versioned_model_path)
    model.save(resolved_model_path)
    storage.upload_file(versioned_model_path, blob_name=versioned_model_blob_name, overwrite=True)
    storage.upload_file(resolved_model_path, blob_name=MODEL_BLOB_NAME, overwrite=True)
    _write_active_model_registry(storage, model_version, versioned_model_blob_name)

    print("Training evaluation plots uploaded to Azure Blob storage.")
    print(f"Trained model saved to: {versioned_model_path}")
    return model_version, report_text


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]

    default_data_path = repo_root / "data" / "health_insurance_data.csv"
    parser = argparse.ArgumentParser(description="Health insurance risk workflow script")
    parser.add_argument(
        "--mode",
        choices=["prep", "eda", "train", "full"],
        default="prep",
        help="prep: data+db, eda: prep+sql+plots, train: prep+training, full: all steps",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=default_data_path,
        help="Path to input CSV data",
    )
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=repo_root / "plots",
        help="Directory for generated plots",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=2000,
        help="Max epochs for neural network training",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.data_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.data_path}")

    df = build_dataset(args.data_path)
    persist_dataset(df)

    if args.mode in {"eda", "full"}:
        run_sql_checks()
        df_analysis = load_analysis_data()
        run_eda(df_analysis, args.plots_dir)

    if args.mode in {"train", "full"}:
        run_training(args.plots_dir, args.epochs)

    print("Workflow completed.")
    print(f"Mode: {args.mode}")
    print(f"Rows processed: {len(df)}")
    print("DB written: Azure SQL")
    print("Risk distribution:")
    print(df["risk_category"].value_counts())


if __name__ == "__main__":
    main()
