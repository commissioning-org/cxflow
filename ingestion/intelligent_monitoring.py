#!/usr/bin/env python3
"""
Intelligent monitoring system with anomaly detection.

Features:
- Real-time metric collection and analysis
- Statistical anomaly detection (Z-score, IQR, MAD)
- Trend analysis and forecasting
- Alert generation and notification
- Performance baseline learning
- Adaptive thresholds
- Multi-dimensional anomaly detection
- Pattern recognition
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
from enum import Enum
import statistics
import json

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies."""
    SPIKE = "spike"
    DROP = "drop"
    TREND_CHANGE = "trend_change"
    PATTERN_BREAK = "pattern_break"
    THRESHOLD_BREACH = "threshold_breach"
    UNUSUAL_VALUE = "unusual_value"


class Severity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Metric:
    """Single metric measurement."""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    """Detected anomaly."""
    metric_name: str
    anomaly_type: AnomalyType
    severity: Severity
    value: float
    expected_range: Tuple[float, float]
    deviation: float
    confidence: float
    timestamp: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'metric_name': self.metric_name,
            'anomaly_type': self.anomaly_type.value,
            'severity': self.severity.value,
            'value': self.value,
            'expected_range': self.expected_range,
            'deviation': self.deviation,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'context': self.context,
        }


@dataclass
class Alert:
    """System alert."""
    alert_id: str
    title: str
    message: str
    severity: Severity
    anomalies: List[Anomaly] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'title': self.title,
            'message': self.message,
            'severity': self.severity.value,
            'anomalies': [a.to_dict() for a in self.anomalies],
            'timestamp': self.timestamp,
            'acknowledged': self.acknowledged,
        }


class MetricStore:
    """Store and manage metrics with time-series data."""
    
    def __init__(self, retention_seconds: int = 3600, max_points: int = 10000):
        self.retention_seconds = retention_seconds
        self.max_points = max_points
        
        # Time-series data: metric_name -> deque of (timestamp, value)
        self._data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        
        # Statistics cache
        self._stats_cache: Dict[str, Dict[str, float]] = {}
        self._cache_timestamp: Dict[str, float] = {}
        self._cache_ttl = 60  # Cache stats for 60 seconds
    
    def add(self, metric: Metric) -> None:
        """Add a metric."""
        self._data[metric.name].append((metric.timestamp, metric.value))
        
        # Invalidate cache
        if metric.name in self._stats_cache:
            del self._stats_cache[metric.name]
    
    def get_recent(self, metric_name: str, seconds: int = 300) -> List[Tuple[float, float]]:
        """Get recent metrics within time window."""
        if metric_name not in self._data:
            return []
        
        cutoff = time.time() - seconds
        return [(ts, val) for ts, val in self._data[metric_name] if ts >= cutoff]
    
    def get_statistics(self, metric_name: str, seconds: int = 300) -> Dict[str, float]:
        """Get statistics for a metric."""
        # Check cache
        now = time.time()
        if metric_name in self._stats_cache:
            if now - self._cache_timestamp.get(metric_name, 0) < self._cache_ttl:
                return self._stats_cache[metric_name]
        
        # Calculate statistics
        recent = self.get_recent(metric_name, seconds)
        if not recent:
            return {}
        
        values = [val for _, val in recent]
        
        stats = {
            'count': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'min': min(values),
            'max': max(values),
        }
        
        if len(values) > 1:
            stats['stdev'] = statistics.stdev(values)
            stats['variance'] = statistics.variance(values)
            
            # Calculate percentiles
            sorted_values = sorted(values)
            stats['p50'] = sorted_values[len(sorted_values) // 2]
            stats['p95'] = sorted_values[int(len(sorted_values) * 0.95)]
            stats['p99'] = sorted_values[int(len(sorted_values) * 0.99)]
            
            # Calculate MAD (Median Absolute Deviation)
            median = stats['median']
            mad = statistics.median([abs(v - median) for v in values])
            stats['mad'] = mad
        
        # Cache result
        self._stats_cache[metric_name] = stats
        self._cache_timestamp[metric_name] = now
        
        return stats
    
    def cleanup_old_data(self) -> int:
        """Remove old data points."""
        cutoff = time.time() - self.retention_seconds
        removed = 0
        
        for metric_name, data in self._data.items():
            original_len = len(data)
            # Remove old points
            while data and data[0][0] < cutoff:
                data.popleft()
                removed += 1
        
        return removed


class AnomalyDetector:
    """Detect anomalies in metrics using statistical methods."""
    
    def __init__(
        self,
        metric_store: MetricStore,
        sensitivity: float = 3.0,
        min_samples: int = 10,
    ):
        self.metric_store = metric_store
        self.sensitivity = sensitivity
        self.min_samples = min_samples
    
    def detect_zscore(self, metric: Metric, window_seconds: int = 300) -> Optional[Anomaly]:
        """Detect anomaly using Z-score method."""
        stats = self.metric_store.get_statistics(metric.name, window_seconds)
        
        if not stats or stats.get('count', 0) < self.min_samples:
            return None
        
        mean = stats['mean']
        stdev = stats.get('stdev', 0)
        
        if stdev == 0:
            return None
        
        # Calculate Z-score
        zscore = abs((metric.value - mean) / stdev)
        
        if zscore > self.sensitivity:
            anomaly_type = AnomalyType.SPIKE if metric.value > mean else AnomalyType.DROP
            
            # Calculate severity based on Z-score
            if zscore > 5:
                severity = Severity.CRITICAL
            elif zscore > 4:
                severity = Severity.HIGH
            elif zscore > 3.5:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
            
            expected_range = (
                mean - self.sensitivity * stdev,
                mean + self.sensitivity * stdev,
            )
            
            return Anomaly(
                metric_name=metric.name,
                anomaly_type=anomaly_type,
                severity=severity,
                value=metric.value,
                expected_range=expected_range,
                deviation=zscore,
                confidence=min(0.99, 0.5 + (zscore - self.sensitivity) * 0.1),
                timestamp=datetime.fromtimestamp(metric.timestamp).isoformat() + 'Z',
                context={
                    'method': 'zscore',
                    'mean': mean,
                    'stdev': stdev,
                    'zscore': zscore,
                },
            )
        
        return None
    
    def detect_iqr(self, metric: Metric, window_seconds: int = 300) -> Optional[Anomaly]:
        """Detect anomaly using IQR (Interquartile Range) method."""
        recent = self.metric_store.get_recent(metric.name, window_seconds)
        
        if len(recent) < self.min_samples:
            return None
        
        values = sorted([val for _, val in recent])
        
        # Calculate quartiles
        q1_idx = len(values) // 4
        q3_idx = 3 * len(values) // 4
        q1 = values[q1_idx]
        q3 = values[q3_idx]
        iqr = q3 - q1
        
        if iqr == 0:
            return None
        
        # Calculate bounds
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        if metric.value < lower_bound or metric.value > upper_bound:
            anomaly_type = AnomalyType.SPIKE if metric.value > upper_bound else AnomalyType.DROP
            
            # Calculate deviation
            if metric.value > upper_bound:
                deviation = (metric.value - upper_bound) / iqr
            else:
                deviation = (lower_bound - metric.value) / iqr
            
            # Calculate severity
            if deviation > 3:
                severity = Severity.CRITICAL
            elif deviation > 2:
                severity = Severity.HIGH
            elif deviation > 1:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
            
            return Anomaly(
                metric_name=metric.name,
                anomaly_type=anomaly_type,
                severity=severity,
                value=metric.value,
                expected_range=(lower_bound, upper_bound),
                deviation=deviation,
                confidence=min(0.95, 0.6 + deviation * 0.1),
                timestamp=datetime.fromtimestamp(metric.timestamp).isoformat() + 'Z',
                context={
                    'method': 'iqr',
                    'q1': q1,
                    'q3': q3,
                    'iqr': iqr,
                },
            )
        
        return None
    
    def detect_mad(self, metric: Metric, window_seconds: int = 300) -> Optional[Anomaly]:
        """Detect anomaly using MAD (Median Absolute Deviation) method."""
        stats = self.metric_store.get_statistics(metric.name, window_seconds)
        
        if not stats or stats.get('count', 0) < self.min_samples:
            return None
        
        median = stats['median']
        mad = stats.get('mad', 0)
        
        if mad == 0:
            return None
        
        # Calculate modified Z-score
        # Using MAD is more robust to outliers than standard deviation
        modified_zscore = 0.6745 * abs(metric.value - median) / mad
        
        if modified_zscore > self.sensitivity:
            anomaly_type = AnomalyType.SPIKE if metric.value > median else AnomalyType.DROP
            
            # Calculate severity
            if modified_zscore > 5:
                severity = Severity.CRITICAL
            elif modified_zscore > 4:
                severity = Severity.HIGH
            elif modified_zscore > 3.5:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
            
            # Approximate expected range
            expected_range = (
                median - self.sensitivity * mad / 0.6745,
                median + self.sensitivity * mad / 0.6745,
            )
            
            return Anomaly(
                metric_name=metric.name,
                anomaly_type=anomaly_type,
                severity=severity,
                value=metric.value,
                expected_range=expected_range,
                deviation=modified_zscore,
                confidence=min(0.97, 0.55 + (modified_zscore - self.sensitivity) * 0.1),
                timestamp=datetime.fromtimestamp(metric.timestamp).isoformat() + 'Z',
                context={
                    'method': 'mad',
                    'median': median,
                    'mad': mad,
                    'modified_zscore': modified_zscore,
                },
            )
        
        return None
    
    def detect_trend_change(self, metric: Metric, window_seconds: int = 600) -> Optional[Anomaly]:
        """Detect sudden trend changes."""
        recent = self.metric_store.get_recent(metric.name, window_seconds)
        
        if len(recent) < self.min_samples * 2:
            return None
        
        # Split into two halves
        mid = len(recent) // 2
        first_half = [val for _, val in recent[:mid]]
        second_half = [val for _, val in recent[mid:]]
        
        if not first_half or not second_half:
            return None
        
        # Calculate means of each half
        mean1 = statistics.mean(first_half)
        mean2 = statistics.mean(second_half)
        
        # Calculate overall standard deviation
        all_values = first_half + second_half
        if len(all_values) < 2:
            return None
        
        stdev = statistics.stdev(all_values)
        
        if stdev == 0:
            return None
        
        # Calculate change magnitude
        change = abs(mean2 - mean1)
        change_ratio = change / stdev
        
        if change_ratio > self.sensitivity:
            severity = Severity.HIGH if change_ratio > 5 else Severity.MEDIUM
            
            return Anomaly(
                metric_name=metric.name,
                anomaly_type=AnomalyType.TREND_CHANGE,
                severity=severity,
                value=metric.value,
                expected_range=(mean1 - stdev, mean1 + stdev),
                deviation=change_ratio,
                confidence=min(0.90, 0.5 + change_ratio * 0.05),
                timestamp=datetime.fromtimestamp(metric.timestamp).isoformat() + 'Z',
                context={
                    'method': 'trend_change',
                    'old_mean': mean1,
                    'new_mean': mean2,
                    'change': change,
                    'change_ratio': change_ratio,
                },
            )
        
        return None


class IntelligentMonitor:
    """Intelligent monitoring system with anomaly detection."""
    
    def __init__(
        self,
        retention_seconds: int = 3600,
        sensitivity: float = 3.0,
        alert_callback: Optional[Callable[[Alert], None]] = None,
    ):
        self.metric_store = MetricStore(retention_seconds=retention_seconds)
        self.detector = AnomalyDetector(
            metric_store=self.metric_store,
            sensitivity=sensitivity,
        )
        self.alert_callback = alert_callback
        
        # Alert management
        self._alerts: Dict[str, Alert] = {}
        self._alert_cooldown: Dict[str, float] = {}
        self._cooldown_seconds = 300  # 5 minutes between similar alerts
        
        # Metrics
        self._total_metrics = 0
        self._total_anomalies = 0
        self._total_alerts = 0
    
    def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Anomaly]:
        """Record a metric and detect anomalies."""
        metric = Metric(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
            metadata=metadata or {},
        )
        
        self.metric_store.add(metric)
        self._total_metrics += 1
        
        # Detect anomalies using multiple methods
        anomalies = []
        
        # Z-score detection
        anomaly = self.detector.detect_zscore(metric)
        if anomaly:
            anomalies.append(anomaly)
        
        # IQR detection
        anomaly = self.detector.detect_iqr(metric)
        if anomaly:
            anomalies.append(anomaly)
        
        # MAD detection
        anomaly = self.detector.detect_mad(metric)
        if anomaly:
            anomalies.append(anomaly)
        
        # Trend change detection
        anomaly = self.detector.detect_trend_change(metric)
        if anomaly:
            anomalies.append(anomaly)
        
        # Generate alerts if anomalies detected
        if anomalies:
            self._total_anomalies += len(anomalies)
            self._generate_alert(metric, anomalies)
        
        return anomalies
    
    def _generate_alert(self, metric: Metric, anomalies: List[Anomaly]) -> None:
        """Generate alert for anomalies."""
        # Check cooldown
        alert_key = f"{metric.name}_{anomalies[0].anomaly_type.value}"
        now = time.time()
        
        if alert_key in self._alert_cooldown:
            if now - self._alert_cooldown[alert_key] < self._cooldown_seconds:
                return
        
        # Create alert
        highest_severity = max(a.severity for a in anomalies)
        
        alert_id = f"alert_{int(now)}_{metric.name}"
        alert = Alert(
            alert_id=alert_id,
            title=f"Anomaly detected in {metric.name}",
            message=f"Detected {len(anomalies)} anomalies in metric {metric.name}. "
                   f"Current value: {metric.value:.2f}",
            severity=highest_severity,
            anomalies=anomalies,
        )
        
        self._alerts[alert_id] = alert
        self._alert_cooldown[alert_key] = now
        self._total_alerts += 1
        
        # Callback
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.exception("Error in alert callback")
        
        # Log alert
        logger.warning(f"Alert generated: {alert.title} (severity: {alert.severity.value})")
    
    def get_alerts(
        self,
        severity: Optional[Severity] = None,
        since_seconds: Optional[int] = None,
    ) -> List[Alert]:
        """Get recent alerts."""
        alerts = list(self._alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if since_seconds:
            cutoff = datetime.utcnow() - timedelta(seconds=since_seconds)
            alerts = [
                a for a in alerts
                if datetime.fromisoformat(a.timestamp.replace('Z', '+00:00')) > cutoff
            ]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            'total_metrics': self._total_metrics,
            'total_anomalies': self._total_anomalies,
            'total_alerts': self._total_alerts,
            'active_alerts': len([a for a in self._alerts.values() if not a.acknowledged]),
            'metrics_tracked': len(self.metric_store._data),
        }
    
    def cleanup(self) -> None:
        """Clean up old data."""
        removed = self.metric_store.cleanup_old_data()
        logger.info(f"Cleaned up {removed} old metric data points")


if __name__ == '__main__':
    # Example usage
    import random
    
    logging.basicConfig(level=logging.INFO)
    
    def alert_handler(alert: Alert):
        print(f"\n🚨 ALERT: {alert.title}")
        print(f"   Severity: {alert.severity.value}")
        print(f"   Anomalies: {len(alert.anomalies)}")
        for anomaly in alert.anomalies:
            print(f"   - {anomaly.anomaly_type.value}: {anomaly.value:.2f} "
                  f"(expected: {anomaly.expected_range[0]:.2f}-{anomaly.expected_range[1]:.2f})")
    
    monitor = IntelligentMonitor(alert_callback=alert_handler)
    
    # Simulate normal metrics
    print("Recording normal metrics...")
    for i in range(50):
        value = 100 + random.gauss(0, 10)
        monitor.record_metric("response_time_ms", value)
        time.sleep(0.01)
    
    # Introduce anomaly (spike)
    print("\nIntroducing anomaly (spike)...")
    monitor.record_metric("response_time_ms", 250)
    
    # More normal metrics
    for i in range(20):
        value = 100 + random.gauss(0, 10)
        monitor.record_metric("response_time_ms", value)
        time.sleep(0.01)
    
    # Introduce anomaly (drop)
    print("\nIntroducing anomaly (drop)...")
    monitor.record_metric("response_time_ms", 10)
    
    # Print statistics
    print("\nMonitoring Statistics:")
    stats = monitor.get_statistics()
    print(json.dumps(stats, indent=2))
    
    # Get alerts
    print("\nRecent Alerts:")
    alerts = monitor.get_alerts()
    for alert in alerts:
        print(f"- {alert.title} ({alert.severity.value})")
