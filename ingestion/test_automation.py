#!/usr/bin/env python3
"""
Integration tests for enhanced automation features.

Tests:
- Auto-validation functionality
- Smart routing with failover
- Auto-transformation pipeline
- Self-healing automation
- Priority queue and batch processing
- Intelligent monitoring
- Resource optimization
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add ingestion directory to path
INGESTION_DIR = Path(__file__).parent
sys.path.insert(0, str(INGESTION_DIR))

# Import modules directly
import auto_transform
import self_healing
import intelligent_monitoring
import resource_optimizer


def test_auto_transform():
    """Test auto-transformation module."""
    print("Testing auto-transformation...")
    
    # Sample data with issues
    rows = [
        {'id': 1, 'name': 'Alice', 'age': 25, 'income': 50000},
        {'id': 2, 'name': 'Bob', 'age': None, 'income': 60000},  # Missing age
        {'id': 3, 'name': 'Charlie', 'age': 30, 'income': 70000},
        {'id': 1, 'name': 'Alice', 'age': 25, 'income': 50000},  # Duplicate
        {'id': 4, 'name': 'David', 'age': 35, 'income': 1000000},  # Outlier
    ]
    
    config = auto_transform.TransformationConfig(
        handle_missing=True,
        missing_strategy="mean",
        handle_outliers=True,
        outlier_action="clip",
        remove_duplicates=True,
    )
    
    transformer = auto_transform.AutoTransformer(config)
    result = transformer.transform(rows)
    
    assert result.ok, "Transformation failed"
    assert result.statistics['duplicates_removed'] > 0, "Should detect duplicates"
    assert len(result.transformed_rows) < len(rows), "Should remove duplicates"
    
    print("  ✓ Auto-transformation working correctly")
    return True


def test_self_healing():
    """Test self-healing automation."""
    print("Testing self-healing automation...")
    
    automation = self_healing.SelfHealingAutomation()
    
    # Register health check
    automation.register_health_check(self_healing.HealthCheck(
        name="test_check",
        check_func=lambda: True,
        critical=False,
    ))
    
    # Test health check
    health = automation.check_health()
    assert 'test_check' in health, "Health check not registered"
    
    # Test operation with retry
    attempt_count = [0]
    
    def failing_operation():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise Exception("Simulated failure")
        return "success"
    
    result = automation.execute_with_recovery(
        operation=failing_operation,
        operation_name="test_operation",
        recovery=self_healing.RecoveryAction(
            strategy=self_healing.RecoveryStrategy.RETRY,
            max_retries=5,
            retry_delay_ms=10,
        ),
    )
    
    assert result.ok, "Operation should succeed after retries"
    assert result.retries > 0, "Should have retried at least once"
    
    print("  ✓ Self-healing automation working correctly")
    return True


def test_intelligent_monitoring():
    """Test intelligent monitoring with anomaly detection."""
    print("Testing intelligent monitoring...")
    
    import random
    
    monitor = intelligent_monitoring.IntelligentMonitor(sensitivity=3.0)
    
    # Record normal metrics
    for i in range(50):
        value = 100 + random.gauss(0, 5)
        monitor.record_metric("test_metric", value)
    
    # Record anomaly
    anomalies = monitor.record_metric("test_metric", 200)
    
    assert len(anomalies) > 0, "Should detect anomaly"
    assert any(a.value == 200 for a in anomalies), "Should detect the spike"
    
    # Check statistics
    stats = monitor.get_statistics()
    assert stats['total_metrics'] >= 51, "Should have recorded metrics"
    assert stats['total_anomalies'] > 0, "Should have detected anomalies"
    
    print("  ✓ Intelligent monitoring working correctly")
    return True


def test_resource_optimizer():
    """Test resource optimizer."""
    print("Testing resource optimizer...")
    
    import time
    
    config = resource_optimizer.OptimizationConfig(
        auto_gc_enabled=True,
        auto_tune_batch_size=True,
    )
    
    optimizer = resource_optimizer.ResourceOptimizer(config)
    
    # Force optimization to happen by setting last optimization time to past
    optimizer._last_optimization = 0
    
    # Record some metrics with cache hit rate
    for i in range(15):
        metrics = resource_optimizer.ResourceMetrics(
            timestamp=time.time(),
            cpu_percent=50 + i,
            memory_percent=0.6 + i * 0.01,
            active_connections=20 + i * 2,
            latency_ms=100 + i * 10,
            cache_hit_rate=0.5 + i * 0.01,  # Add cache hit rate
        )
        optimizer.record_metrics(metrics)
    
    # Run optimization
    result = optimizer.optimize()
    assert 'timestamp' in result or 'optimized' in result, "Should return optimization result"
    
    # Get recommendations
    recommendations = optimizer.get_recommendations()
    assert 'recommendations' in recommendations, "Should provide recommendations"
    
    # Get statistics
    stats = optimizer.get_statistics()
    assert stats['metrics_collected'] >= 15, "Should have collected metrics"
    
    print("  ✓ Resource optimizer working correctly")
    return True


def test_smart_routing():
    """Test smart routing module."""
    print("Testing smart routing...")
    
    # This test uses PHP module, so we'll just verify it exists and is valid
    import subprocess
    
    result = subprocess.run(
        ['php', '-l', 'ingestion/smart_routing.php'],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, f"PHP syntax error: {result.stderr}"
    
    print("  ✓ Smart routing module syntax valid")
    return True


def test_auto_validation():
    """Test auto-validation module."""
    print("Testing auto-validation...")
    
    # This test uses PHP module, so we'll just verify it exists and is valid
    import subprocess
    
    result = subprocess.run(
        ['php', '-l', 'ingestion/auto_validation.php'],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, f"PHP syntax error: {result.stderr}"
    
    print("  ✓ Auto-validation module syntax valid")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Enhanced Automation Integration Tests")
    print("=" * 60 + "\n")
    
    tests = [
        ("Auto-Transformation", test_auto_transform),
        ("Self-Healing", test_self_healing),
        ("Intelligent Monitoring", test_intelligent_monitoring),
        ("Resource Optimizer", test_resource_optimizer),
        ("Smart Routing", test_smart_routing),
        ("Auto-Validation", test_auto_validation),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
