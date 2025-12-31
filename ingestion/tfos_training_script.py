#!/usr/bin/env python3
"""
TensorFlowOnSpark Training Script.

Generic training script that integrates with CX ingestion pipeline data.
Supports both InputMode.TENSORFLOW and InputMode.SPARK.

Reference: https://github.com/yahoo/TensorFlowOnSpark

Usage:
    spark-submit \\
        --master spark://localhost:7077 \\
        tfos_training_script.py \\
        --cluster_size 2 \\
        --epochs 5 \\
        --data_path /path/to/data.ndjson \\
        --target_column label \\
        --model_dir /path/to/model \\
        --export_dir /path/to/export
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# TensorFlow imports
try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError:
    print("TensorFlow not installed. Please install with: pip install tensorflow")
    sys.exit(1)

# TensorFlowOnSpark imports
try:
    from tensorflowonspark import TFCluster, TFNode
    from tensorflowonspark.pipeline import TFEstimator, TFModel
except ImportError:
    TFCluster = None
    TFNode = None
    TFEstimator = None
    TFModel = None
    print("WARNING: TensorFlowOnSpark not installed. Running in standalone mode.")

# PySpark imports
try:
    from pyspark.context import SparkContext
    from pyspark.conf import SparkConf
    from pyspark.sql import SparkSession
except ImportError:
    SparkContext = None
    SparkConf = None
    SparkSession = None
    print("WARNING: PySpark not installed. Running in standalone mode.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tfos_training")


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


def load_ndjson(path: str, max_rows: int = 0) -> list[dict[str, Any]]:
    """Load NDJSON file into list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if max_rows > 0 and len(rows) >= max_rows:
                break
    return rows


def load_csv(path: str, max_rows: int = 0) -> list[dict[str, Any]]:
    """Load CSV file into list of dicts."""
    import csv

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
            if max_rows > 0 and len(rows) >= max_rows:
                break
    return rows


def load_data(path: str, format: str = "ndjson", max_rows: int = 0) -> list[dict[str, Any]]:
    """Load data from file."""
    if format == "csv":
        return load_csv(path, max_rows)
    return load_ndjson(path, max_rows)


def rows_to_numpy(
    rows: list[dict[str, Any]], target_column: str, feature_columns: list[str] | None = None
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Convert list of dicts to numpy arrays for training."""
    if not rows:
        raise ValueError("No data rows provided")

    # Infer feature columns if not provided
    if not feature_columns:
        all_cols = set()
        for row in rows:
            all_cols.update(row.keys())
        feature_columns = sorted([c for c in all_cols if c != target_column])

    # Extract features and labels
    X = []
    y = []

    for row in rows:
        features = []
        for col in feature_columns:
            val = row.get(col)
            # Convert to float, handling strings
            if val is None:
                features.append(0.0)
            elif isinstance(val, (int, float)):
                features.append(float(val))
            elif isinstance(val, str):
                try:
                    features.append(float(val))
                except ValueError:
                    # Encode string as hash (simple approach)
                    features.append(float(hash(val) % 10000))
            else:
                features.append(0.0)
        X.append(features)

        # Target
        label = row.get(target_column)
        if label is None:
            y.append(0)
        elif isinstance(label, (int, float)):
            y.append(label)
        elif isinstance(label, str):
            try:
                y.append(float(label))
            except ValueError:
                y.append(hash(label) % 100)
        else:
            y.append(0)

    return np.array(X, dtype=np.float32), np.array(y), feature_columns


# ---------------------------------------------------------------------------
# Model Building
# ---------------------------------------------------------------------------


def build_classification_model(input_dim: int, num_classes: int) -> keras.Model:
    """Build a simple classification model."""
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(input_dim,)),
            keras.layers.Dense(128, activation="relu"),
            keras.layers.Dropout(0.3),
            keras.layers.Dense(64, activation="relu"),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(32, activation="relu"),
            keras.layers.Dense(num_classes, activation="softmax"),
        ]
    )
    return model


def build_regression_model(input_dim: int) -> keras.Model:
    """Build a simple regression model."""
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(input_dim,)),
            keras.layers.Dense(128, activation="relu"),
            keras.layers.Dropout(0.3),
            keras.layers.Dense(64, activation="relu"),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(32, activation="relu"),
            keras.layers.Dense(1),
        ]
    )
    return model


def infer_problem_type(y: np.ndarray) -> str:
    """Infer classification vs regression."""
    unique = np.unique(y)
    if len(unique) <= 20 or (np.all(y == y.astype(int)) and len(unique) < len(y) * 0.1):
        return "classification"
    return "regression"


# ---------------------------------------------------------------------------
# TFoS Main Function
# ---------------------------------------------------------------------------


def main_fun(args: argparse.Namespace, ctx: Any) -> None:
    """
    TensorFlow main function for TFoS distributed training.

    This function runs on each Spark executor. The `ctx` object provides
    TFoS context including cluster_spec, job_name, task_index, etc.

    Args:
        args: Parsed command-line arguments
        ctx: TFNodeContext from TensorFlowOnSpark
    """
    import tensorflow as tf
    from tensorflow import keras

    # Get worker info from context
    job_name = ctx.job_name if hasattr(ctx, "job_name") else "worker"
    task_index = ctx.task_index if hasattr(ctx, "task_index") else 0
    cluster_spec = ctx.cluster_spec if hasattr(ctx, "cluster_spec") else {}

    logger.info(f"Starting TFoS worker: job={job_name}, task={task_index}")
    logger.info(f"Cluster spec: {cluster_spec}")

    # Set up TF_CONFIG for multi-worker training
    if cluster_spec:
        tf_config = {
            "cluster": cluster_spec,
            "task": {"type": job_name, "index": task_index},
        }
        os.environ["TF_CONFIG"] = json.dumps(tf_config)
        logger.info(f"TF_CONFIG set: {tf_config}")

    # Distribution strategy
    strategy = tf.distribute.MultiWorkerMirroredStrategy()
    logger.info(f"Using strategy: {strategy}")

    # Load data
    if args.input_mode == "SPARK":
        # Data fed via TFNode.DataFeed
        tf_feed = TFNode.DataFeed(ctx.mgr, False)
        rows = []
        while not tf_feed.should_stop():
            batch = tf_feed.next_batch(batch_size=args.batch_size)
            if batch:
                rows.extend(batch)
        logger.info(f"Received {len(rows)} rows from Spark")
    else:
        # Load data directly (InputMode.TENSORFLOW)
        rows = load_data(args.data_path, args.format)
        logger.info(f"Loaded {len(rows)} rows from {args.data_path}")

    if not rows:
        logger.error("No data available for training")
        return

    # Prepare numpy arrays
    X, y, feature_columns = rows_to_numpy(rows, args.target_column)
    logger.info(f"Data shape: X={X.shape}, y={y.shape}")
    logger.info(f"Features: {feature_columns}")

    # Infer problem type
    problem_type = infer_problem_type(y)
    logger.info(f"Problem type: {problem_type}")

    # Build model within strategy scope
    with strategy.scope():
        if problem_type == "classification":
            num_classes = len(np.unique(y))
            y = y.astype(np.int32)
            model = build_classification_model(X.shape[1], num_classes)
            model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=args.learning_rate),
                loss="sparse_categorical_crossentropy",
                metrics=["accuracy"],
            )
        else:
            model = build_regression_model(X.shape[1])
            model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=args.learning_rate),
                loss="mse",
                metrics=["mae"],
            )

    model.summary(print_fn=logger.info)

    # Callbacks
    callbacks = []

    # ModelCheckpoint
    if args.model_dir:
        os.makedirs(args.model_dir, exist_ok=True)
        checkpoint_path = os.path.join(args.model_dir, "checkpoint_{epoch:02d}")
        callbacks.append(
            keras.callbacks.ModelCheckpoint(
                checkpoint_path,
                save_weights_only=True,
                save_best_only=False,
            )
        )

    # TensorBoard
    if args.tensorboard and args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)
        callbacks.append(keras.callbacks.TensorBoard(log_dir=args.log_dir))

    # Train
    logger.info(f"Training for {args.epochs} epochs, batch_size={args.batch_size}")
    history = model.fit(
        X,
        y,
        epochs=args.epochs,
        batch_size=args.batch_size,
        validation_split=0.2,
        callbacks=callbacks,
        verbose=1 if task_index == 0 else 0,
    )

    # Only chief worker saves the model
    is_chief = job_name in ("chief", "master") or (job_name == "worker" and task_index == 0)

    if is_chief:
        logger.info("Chief worker saving model...")

        # Save Keras model
        if args.model_dir:
            model_path = os.path.join(args.model_dir, "model.keras")
            model.save(model_path)
            logger.info(f"Saved Keras model to {model_path}")

        # Export SavedModel
        if args.export_dir:
            os.makedirs(args.export_dir, exist_ok=True)
            model.export(args.export_dir)
            logger.info(f"Exported SavedModel to {args.export_dir}")

        # Save training history
        if args.model_dir:
            history_path = os.path.join(args.model_dir, "history.json")
            history_data = {k: [float(v) for v in vals] for k, vals in history.history.items()}
            with open(history_path, "w") as f:
                json.dump(history_data, f, indent=2)
            logger.info(f"Saved history to {history_path}")

            # Save metadata
            meta_path = os.path.join(args.model_dir, "metadata.json")
            metadata = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "problem_type": problem_type,
                "input_dim": int(X.shape[1]),
                "num_classes": int(num_classes) if problem_type == "classification" else None,
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "feature_columns": feature_columns,
                "target_column": args.target_column,
                "row_count": len(rows),
                "final_metrics": {k: float(v[-1]) for k, v in history.history.items()},
            }
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Saved metadata to {meta_path}")

    logger.info("Training complete!")


# ---------------------------------------------------------------------------
# Standalone Training (without Spark)
# ---------------------------------------------------------------------------


def standalone_train(args: argparse.Namespace) -> None:
    """Run training without Spark (single-node)."""
    logger.info("Running in standalone mode (no Spark)")

    # Load data
    rows = load_data(args.data_path, args.format)
    logger.info(f"Loaded {len(rows)} rows")

    if not rows:
        logger.error("No data available")
        return

    # Prepare data
    X, y, feature_columns = rows_to_numpy(rows, args.target_column)
    logger.info(f"Data shape: X={X.shape}, y={y.shape}")

    # Split
    from sklearn.model_selection import train_test_split

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    # Infer problem type
    problem_type = infer_problem_type(y)
    logger.info(f"Problem type: {problem_type}")

    # Build model
    if problem_type == "classification":
        num_classes = len(np.unique(y))
        y_train = y_train.astype(np.int32)
        y_val = y_val.astype(np.int32)
        model = build_classification_model(X.shape[1], num_classes)
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=args.learning_rate),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )
    else:
        num_classes = 0
        model = build_regression_model(X.shape[1])
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=args.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

    model.summary()

    # Train
    callbacks = []
    if args.model_dir:
        os.makedirs(args.model_dir, exist_ok=True)

    history = model.fit(
        X_train,
        y_train,
        epochs=args.epochs,
        batch_size=args.batch_size,
        validation_data=(X_val, y_val),
        callbacks=callbacks,
        verbose=1,
    )

    # Save model
    if args.model_dir:
        model_path = os.path.join(args.model_dir, "model.keras")
        model.save(model_path)
        logger.info(f"Saved model to {model_path}")

    if args.export_dir:
        os.makedirs(args.export_dir, exist_ok=True)
        model.export(args.export_dir)
        logger.info(f"Exported to {args.export_dir}")

    # Save metadata
    if args.model_dir:
        meta_path = os.path.join(args.model_dir, "metadata.json")
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "problem_type": problem_type,
            "input_dim": int(X.shape[1]),
            "num_classes": int(num_classes) if problem_type == "classification" else None,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "feature_columns": feature_columns,
            "target_column": args.target_column,
            "row_count": len(rows),
            "final_metrics": {k: float(v[-1]) for k, v in history.history.items()},
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to {meta_path}")

    logger.info("Standalone training complete!")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="TensorFlowOnSpark Training Script")

    # Cluster configuration
    parser.add_argument("--cluster_size", type=int, default=2, help="Number of TF workers")
    parser.add_argument("--num_ps", type=int, default=0, help="Number of parameter servers")
    parser.add_argument("--input_mode", type=str, default="SPARK", choices=["SPARK", "TENSORFLOW"])
    parser.add_argument("--master_node", type=str, default="chief", help="Master node type")

    # Training configuration
    parser.add_argument("--epochs", type=int, default=5, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size")
    parser.add_argument("--buffer_size", type=int, default=10000, help="Shuffle buffer size")
    parser.add_argument("--learning_rate", type=float, default=0.001, help="Learning rate")

    # Data configuration
    parser.add_argument("--data_path", type=str, required=True, help="Path to training data")
    parser.add_argument("--format", type=str, default="ndjson", choices=["ndjson", "csv", "tfr"])
    parser.add_argument("--target_column", type=str, default="label", help="Target column name")

    # Output configuration
    parser.add_argument("--model_dir", type=str, default="/tmp/tfos_model", help="Model checkpoint dir")
    parser.add_argument("--export_dir", type=str, default="/tmp/tfos_export", help="SavedModel export dir")
    parser.add_argument("--log_dir", type=str, default="/tmp/tfos_logs", help="TensorBoard log dir")

    # Flags
    parser.add_argument("--tensorboard", action="store_true", help="Enable TensorBoard")
    parser.add_argument("--standalone", action="store_true", help="Run without Spark")

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    logger.info(f"TFoS Training Script starting...")
    logger.info(f"Arguments: {args}")

    # Check for standalone mode
    if args.standalone or SparkContext is None or TFCluster is None:
        standalone_train(args)
        return

    # Initialize Spark
    conf = SparkConf().setAppName("CXFlow-TFoS-Training")
    sc = SparkContext(conf=conf)

    # Get executor count from Spark
    executors = sc._conf.get("spark.executor.instances")
    num_executors = int(executors) if executors else args.cluster_size

    logger.info(f"Spark context initialized with {num_executors} executors")

    try:
        if args.input_mode == "SPARK":
            # Load data into Spark RDD
            spark = SparkSession.builder.getOrCreate()

            if args.format == "csv":
                df = spark.read.csv(args.data_path, header=True, inferSchema=True)
            else:
                # NDJSON
                df = spark.read.json(args.data_path)

            logger.info(f"Loaded DataFrame with {df.count()} rows")
            df.printSchema()

            # Run TFoS cluster
            cluster = TFCluster.run(
                sc,
                main_fun,
                args,
                num_executors,
                args.num_ps,
                tensorboard=args.tensorboard,
                input_mode=TFCluster.InputMode.SPARK,
                log_dir=args.log_dir,
                master_node=args.master_node,
            )

            # Feed data to TF workers
            cluster.train(df.rdd, num_epochs=args.epochs)

            # Shutdown
            cluster.shutdown(grace_secs=30)

        else:
            # InputMode.TENSORFLOW - workers load data themselves
            cluster = TFCluster.run(
                sc,
                main_fun,
                args,
                num_executors,
                args.num_ps,
                tensorboard=args.tensorboard,
                input_mode=TFCluster.InputMode.TENSORFLOW,
                log_dir=args.log_dir,
                master_node=args.master_node,
            )

            # Just wait for workers to finish
            cluster.shutdown(grace_secs=30)

    finally:
        sc.stop()

    logger.info("TFoS training complete!")


if __name__ == "__main__":
    main()
