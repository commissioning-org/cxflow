#!/usr/bin/env python3
"""
Automated data transformation pipeline with schema detection and intelligent transformations.

Features:
- Automatic schema detection and mapping
- Data type inference and conversion
- Missing value handling with multiple strategies
- Outlier detection and handling
- Feature engineering and extraction
- Data normalization and standardization
- Duplicate detection and removal
- Auto-encoding of categorical variables
- Time series feature extraction
- Text preprocessing and feature extraction
"""

import json
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransformationConfig:
    """Configuration for data transformation."""
    
    # Missing value handling
    handle_missing: bool = True
    missing_strategy: str = "auto"  # auto, drop, mean, median, mode, forward_fill, constant
    missing_constant: Any = 0
    
    # Outlier handling
    handle_outliers: bool = True
    outlier_method: str = "iqr"  # iqr, zscore, isolation
    outlier_action: str = "clip"  # clip, remove, flag
    
    # Type conversion
    auto_convert_types: bool = True
    infer_dates: bool = True
    
    # Deduplication
    remove_duplicates: bool = True
    duplicate_subset: Optional[List[str]] = None
    
    # Normalization
    normalize_numeric: bool = False
    normalization_method: str = "minmax"  # minmax, zscore, robust
    
    # Feature engineering
    extract_datetime_features: bool = True
    encode_categorical: bool = True
    encoding_method: str = "onehot"  # onehot, label, target
    
    # Text processing
    process_text: bool = True
    text_lowercase: bool = True
    text_remove_special: bool = True


@dataclass
class TransformationResult:
    """Result of data transformation."""
    
    ok: bool
    transformed_rows: List[Dict[str, Any]] = field(default_factory=list)
    original_shape: Tuple[int, int] = (0, 0)
    final_shape: Tuple[int, int] = (0, 0)
    transformations_applied: List[str] = field(default_factory=list)
    schema_changes: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    elapsed_ms: int = 0
    timestamp: str = ""


class AutoTransformer:
    """Automated data transformation pipeline."""
    
    def __init__(self, config: Optional[TransformationConfig] = None):
        self.config = config or TransformationConfig()
        self.schema: Dict[str, Any] = {}
        self.statistics: Dict[str, Any] = {}
        
    def transform(self, rows: List[Dict[str, Any]]) -> TransformationResult:
        """Apply automated transformations to data."""
        start_time = datetime.now()
        
        result = TransformationResult(
            ok=True,
            original_shape=(len(rows), len(rows[0]) if rows else 0),
            timestamp=datetime.utcnow().isoformat() + 'Z',
        )
        
        if not rows:
            result.ok = False
            result.warnings.append("Empty dataset")
            return result
        
        try:
            # Step 1: Detect schema
            self.schema = self._detect_schema(rows)
            result.schema_changes['original_schema'] = self.schema.copy()
            
            # Step 2: Auto-convert types
            if self.config.auto_convert_types:
                rows = self._auto_convert_types(rows)
                result.transformations_applied.append("auto_type_conversion")
            
            # Step 3: Handle missing values
            if self.config.handle_missing:
                rows, missing_stats = self._handle_missing_values(rows)
                result.statistics['missing_values'] = missing_stats
                result.transformations_applied.append(f"missing_values_{self.config.missing_strategy}")
            
            # Step 4: Remove duplicates
            if self.config.remove_duplicates:
                rows, dup_count = self._remove_duplicates(rows)
                result.statistics['duplicates_removed'] = dup_count
                if dup_count > 0:
                    result.transformations_applied.append("deduplication")
            
            # Step 5: Handle outliers
            if self.config.handle_outliers:
                rows, outlier_stats = self._handle_outliers(rows)
                result.statistics['outliers'] = outlier_stats
                result.transformations_applied.append(f"outliers_{self.config.outlier_method}")
            
            # Step 6: Extract datetime features
            if self.config.extract_datetime_features:
                rows = self._extract_datetime_features(rows)
                if self._has_datetime_columns():
                    result.transformations_applied.append("datetime_feature_extraction")
            
            # Step 7: Process text fields
            if self.config.process_text:
                rows = self._process_text_fields(rows)
                if self._has_text_columns():
                    result.transformations_applied.append("text_processing")
            
            # Step 8: Encode categorical variables
            if self.config.encode_categorical:
                rows = self._encode_categorical(rows)
                if self._has_categorical_columns():
                    result.transformations_applied.append(f"categorical_{self.config.encoding_method}")
            
            # Step 9: Normalize numeric features
            if self.config.normalize_numeric:
                rows = self._normalize_numeric(rows)
                result.transformations_applied.append(f"normalization_{self.config.normalization_method}")
            
            # Update result
            result.transformed_rows = rows
            result.final_shape = (len(rows), len(rows[0]) if rows else 0)
            result.schema_changes['final_schema'] = self._detect_schema(rows)
            
        except Exception as e:
            result.ok = False
            result.warnings.append(f"Transformation error: {str(e)}")
            logger.exception("Transformation failed")
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result.elapsed_ms = int(elapsed)
        
        return result
    
    def _detect_schema(self, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Detect schema from data sample."""
        if not rows:
            return {}
        
        schema = {}
        sample = rows[:min(100, len(rows))]
        
        all_keys = set()
        for row in sample:
            all_keys.update(row.keys())
        
        for key in all_keys:
            values = [row.get(key) for row in sample if key in row and row[key] is not None]
            
            if not values:
                schema[key] = {'type': 'unknown', 'nullable': True}
                continue
            
            # Infer type
            inferred_type = self._infer_type(values)
            
            schema[key] = {
                'type': inferred_type,
                'nullable': len(values) < len(sample),
                'sample_values': values[:3],
            }
            
            # Add statistics for numeric types
            if inferred_type in ('int', 'float'):
                numeric_values = [float(v) for v in values if self._is_numeric(v)]
                if numeric_values:
                    schema[key].update({
                        'min': min(numeric_values),
                        'max': max(numeric_values),
                        'mean': sum(numeric_values) / len(numeric_values),
                    })
            
            # Add statistics for categorical types
            elif inferred_type == 'categorical':
                unique_values = set(str(v) for v in values)
                schema[key]['unique_count'] = len(unique_values)
                schema[key]['cardinality'] = len(unique_values) / len(values)
        
        return schema
    
    def _infer_type(self, values: List[Any]) -> str:
        """Infer data type from values."""
        if not values:
            return 'unknown'
        
        # Check for datetime
        if self.config.infer_dates and all(self._is_datetime(v) for v in values[:10]):
            return 'datetime'
        
        # Check for numeric
        if all(self._is_numeric(v) for v in values):
            if all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in values):
                return 'int'
            return 'float'
        
        # Check for boolean
        if all(isinstance(v, bool) or str(v).lower() in ('true', 'false', '1', '0', 'yes', 'no') for v in values):
            return 'boolean'
        
        # Check for categorical (low cardinality strings)
        if all(isinstance(v, str) for v in values):
            unique_ratio = len(set(values)) / len(values)
            if unique_ratio < 0.5:  # Less than 50% unique values
                return 'categorical'
        
        return 'string'
    
    def _is_numeric(self, value: Any) -> bool:
        """Check if value is numeric."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if isinstance(value, str):
            try:
                float(value)
                return True
            except (ValueError, TypeError):
                pass
        return False
    
    def _is_datetime(self, value: Any) -> bool:
        """Check if value is a datetime."""
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            # Common datetime patterns
            patterns = [
                r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
                r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO format
            ]
            return any(re.match(pattern, value) for pattern in patterns)
        return False
    
    def _auto_convert_types(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Automatically convert data types."""
        converted_rows = []
        
        for row in rows:
            converted_row = {}
            for key, value in row.items():
                if value is None:
                    converted_row[key] = value
                    continue
                
                schema_type = self.schema.get(key, {}).get('type', 'unknown')
                
                try:
                    if schema_type == 'int':
                        converted_row[key] = int(float(value))
                    elif schema_type == 'float':
                        converted_row[key] = float(value)
                    elif schema_type == 'boolean':
                        converted_row[key] = self._to_bool(value)
                    elif schema_type == 'datetime':
                        converted_row[key] = self._parse_datetime(value)
                    else:
                        converted_row[key] = value
                except (ValueError, TypeError):
                    converted_row[key] = value  # Keep original if conversion fails
            
            converted_rows.append(converted_row)
        
        return converted_rows
    
    def _to_bool(self, value: Any) -> bool:
        """Convert value to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'y', 'on')
        return bool(value)
    
    def _parse_datetime(self, value: Any) -> Optional[str]:
        """Parse datetime to ISO format string."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            # Try common formats
            formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%m/%d/%Y',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue
        return None
    
    def _handle_missing_values(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Handle missing values."""
        stats = {'total_missing': 0, 'by_column': {}}
        
        # Count missing values
        for row in rows:
            for key in self.schema.keys():
                value = row.get(key)
                if value is None or value == '' or (isinstance(value, float) and value != value):  # NaN check
                    stats['total_missing'] += 1
                    stats['by_column'][key] = stats['by_column'].get(key, 0) + 1
        
        # Apply strategy
        if self.config.missing_strategy == "drop":
            rows = [row for row in rows if not any(
                row.get(k) is None or row.get(k) == '' for k in self.schema.keys()
            )]
        
        elif self.config.missing_strategy in ("mean", "median", "mode"):
            # Calculate statistics per column
            column_stats = {}
            for key, schema in self.schema.items():
                if schema['type'] in ('int', 'float'):
                    values = [row[key] for row in rows if key in row and self._is_numeric(row[key])]
                    if values:
                        if self.config.missing_strategy == "mean":
                            column_stats[key] = sum(values) / len(values)
                        elif self.config.missing_strategy == "median":
                            sorted_values = sorted(values)
                            mid = len(sorted_values) // 2
                            column_stats[key] = sorted_values[mid]
                        elif self.config.missing_strategy == "mode":
                            column_stats[key] = Counter(values).most_common(1)[0][0]
            
            # Fill missing values
            for row in rows:
                for key, fill_value in column_stats.items():
                    if key in row and (row[key] is None or row[key] == ''):
                        row[key] = fill_value
        
        elif self.config.missing_strategy == "constant":
            for row in rows:
                for key in self.schema.keys():
                    if key in row and (row[key] is None or row[key] == ''):
                        row[key] = self.config.missing_constant
        
        return rows, stats
    
    def _remove_duplicates(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """Remove duplicate rows."""
        seen_hashes = set()
        unique_rows = []
        dup_count = 0
        
        for row in rows:
            # Create hash of row content
            if self.config.duplicate_subset:
                row_subset = {k: row.get(k) for k in self.config.duplicate_subset if k in row}
            else:
                row_subset = row
            
            row_hash = hashlib.md5(json.dumps(row_subset, sort_keys=True).encode()).hexdigest()
            
            if row_hash not in seen_hashes:
                seen_hashes.add(row_hash)
                unique_rows.append(row)
            else:
                dup_count += 1
        
        return unique_rows, dup_count
    
    def _handle_outliers(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Handle outliers in numeric columns."""
        stats = {'outliers_detected': 0, 'by_column': {}}
        
        for key, schema in self.schema.items():
            if schema['type'] not in ('int', 'float'):
                continue
            
            values = [float(row[key]) for row in rows if key in row and self._is_numeric(row[key])]
            if len(values) < 10:
                continue
            
            # Detect outliers using IQR method
            sorted_values = sorted(values)
            q1_idx = len(sorted_values) // 4
            q3_idx = 3 * len(sorted_values) // 4
            q1 = sorted_values[q1_idx]
            q3 = sorted_values[q3_idx]
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outlier_count = sum(1 for v in values if v < lower_bound or v > upper_bound)
            
            if outlier_count > 0:
                stats['outliers_detected'] += outlier_count
                stats['by_column'][key] = {
                    'count': outlier_count,
                    'lower_bound': lower_bound,
                    'upper_bound': upper_bound,
                }
                
                # Apply action
                if self.config.outlier_action == "clip":
                    for row in rows:
                        if key in row and self._is_numeric(row[key]):
                            value = float(row[key])
                            if value < lower_bound:
                                row[key] = lower_bound
                            elif value > upper_bound:
                                row[key] = upper_bound
                
                elif self.config.outlier_action == "flag":
                    for row in rows:
                        if key in row and self._is_numeric(row[key]):
                            value = float(row[key])
                            if value < lower_bound or value > upper_bound:
                                row[f'{key}_is_outlier'] = True
        
        if self.config.outlier_action == "remove":
            # Remove rows with any outliers
            filtered_rows = []
            for row in rows:
                is_outlier = False
                for key, outlier_info in stats['by_column'].items():
                    if key in row and self._is_numeric(row[key]):
                        value = float(row[key])
                        if value < outlier_info['lower_bound'] or value > outlier_info['upper_bound']:
                            is_outlier = True
                            break
                if not is_outlier:
                    filtered_rows.append(row)
            rows = filtered_rows
        
        return rows, stats
    
    def _extract_datetime_features(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract features from datetime columns."""
        datetime_cols = [k for k, v in self.schema.items() if v.get('type') == 'datetime']
        
        for row in rows:
            for key in datetime_cols:
                if key not in row or row[key] is None:
                    continue
                
                dt_str = row[key]
                dt = self._parse_datetime(dt_str)
                if dt:
                    dt_obj = datetime.fromisoformat(dt)
                    row[f'{key}_year'] = dt_obj.year
                    row[f'{key}_month'] = dt_obj.month
                    row[f'{key}_day'] = dt_obj.day
                    row[f'{key}_hour'] = dt_obj.hour
                    row[f'{key}_dayofweek'] = dt_obj.weekday()
                    row[f'{key}_quarter'] = (dt_obj.month - 1) // 3 + 1
        
        return rows
    
    def _process_text_fields(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process text fields."""
        text_cols = [k for k, v in self.schema.items() if v.get('type') == 'string']
        
        for row in rows:
            for key in text_cols:
                if key not in row or not isinstance(row[key], str):
                    continue
                
                text = row[key]
                
                if self.config.text_lowercase:
                    text = text.lower()
                
                if self.config.text_remove_special:
                    text = re.sub(r'[^\w\s]', '', text)
                
                row[key] = text.strip()
                
                # Add text features
                row[f'{key}_length'] = len(text)
                row[f'{key}_word_count'] = len(text.split())
        
        return rows
    
    def _encode_categorical(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Encode categorical variables."""
        categorical_cols = [k for k, v in self.schema.items() if v.get('type') == 'categorical']
        
        if self.config.encoding_method == "label":
            # Label encoding
            label_maps = {}
            for key in categorical_cols:
                unique_values = list(set(str(row.get(key, '')) for row in rows if key in row))
                label_maps[key] = {val: idx for idx, val in enumerate(unique_values)}
            
            for row in rows:
                for key in categorical_cols:
                    if key in row:
                        row[f'{key}_encoded'] = label_maps[key].get(str(row[key]), -1)
        
        elif self.config.encoding_method == "onehot":
            # One-hot encoding (for low cardinality only)
            for key in categorical_cols:
                unique_values = list(set(str(row.get(key, '')) for row in rows if key in row))
                if len(unique_values) > 10:  # Skip high cardinality
                    continue
                
                for row in rows:
                    current_value = str(row.get(key, ''))
                    for unique_val in unique_values:
                        row[f'{key}_{unique_val}'] = 1 if current_value == unique_val else 0
        
        return rows
    
    def _normalize_numeric(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize numeric columns."""
        numeric_cols = [k for k, v in self.schema.items() if v.get('type') in ('int', 'float')]
        
        # Calculate statistics
        col_stats = {}
        for key in numeric_cols:
            values = [float(row[key]) for row in rows if key in row and self._is_numeric(row[key])]
            if not values:
                continue
            
            col_stats[key] = {
                'min': min(values),
                'max': max(values),
                'mean': sum(values) / len(values),
                'std': (sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values)) ** 0.5,
            }
        
        # Apply normalization
        for row in rows:
            for key, stats in col_stats.items():
                if key not in row or not self._is_numeric(row[key]):
                    continue
                
                value = float(row[key])
                
                if self.config.normalization_method == "minmax":
                    # Min-max scaling to [0, 1]
                    range_val = stats['max'] - stats['min']
                    if range_val > 0:
                        row[f'{key}_normalized'] = (value - stats['min']) / range_val
                    else:
                        row[f'{key}_normalized'] = 0.0
                
                elif self.config.normalization_method == "zscore":
                    # Z-score standardization
                    if stats['std'] > 0:
                        row[f'{key}_normalized'] = (value - stats['mean']) / stats['std']
                    else:
                        row[f'{key}_normalized'] = 0.0
        
        return rows
    
    def _has_datetime_columns(self) -> bool:
        """Check if schema has datetime columns."""
        return any(v.get('type') == 'datetime' for v in self.schema.values())
    
    def _has_text_columns(self) -> bool:
        """Check if schema has text columns."""
        return any(v.get('type') == 'string' for v in self.schema.values())
    
    def _has_categorical_columns(self) -> bool:
        """Check if schema has categorical columns."""
        return any(v.get('type') == 'categorical' for v in self.schema.values())


def transform_ingestion_data(
    input_path: str,
    output_path: str,
    config: Optional[TransformationConfig] = None
) -> TransformationResult:
    """Transform ingestion data from NDJSON file."""
    
    # Load data
    rows = []
    with open(input_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    # Transform
    transformer = AutoTransformer(config)
    result = transformer.transform(rows)
    
    # Save transformed data
    if result.ok and result.transformed_rows:
        with open(output_path, 'w') as f:
            for row in result.transformed_rows:
                f.write(json.dumps(row) + '\n')
    
    return result


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python auto_transform.py <input.ndjson> <output.ndjson>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    config = TransformationConfig(
        handle_missing=True,
        missing_strategy="mean",
        handle_outliers=True,
        remove_duplicates=True,
        extract_datetime_features=True,
        encode_categorical=True,
        process_text=True,
    )
    
    result = transform_ingestion_data(input_file, output_file, config)
    
    print(json.dumps({
        'ok': result.ok,
        'transformations_applied': result.transformations_applied,
        'original_shape': result.original_shape,
        'final_shape': result.final_shape,
        'statistics': result.statistics,
        'elapsed_ms': result.elapsed_ms,
    }, indent=2))
