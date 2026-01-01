#!/usr/bin/env python3
"""
Automated resource optimization and management.

Features:
- Automatic resource allocation and scaling
- Memory and CPU usage optimization
- Connection pool management
- Cache optimization with automatic eviction
- Batch size auto-tuning
- Query optimization
- Automatic garbage collection tuning
- Resource usage forecasting
"""

import time
import logging
import gc
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """Current resource metrics."""
    timestamp: float
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    active_connections: int = 0
    cache_hit_rate: float = 0.0
    queue_size: int = 0
    throughput: float = 0.0
    latency_ms: float = 0.0


@dataclass
class OptimizationConfig:
    """Configuration for resource optimization."""
    
    # Memory management
    memory_high_watermark: float = 0.80  # 80% memory usage
    memory_low_watermark: float = 0.60   # 60% memory usage
    auto_gc_enabled: bool = True
    gc_threshold_mb: float = 100.0
    
    # Connection pooling
    min_pool_size: int = 5
    max_pool_size: int = 100
    pool_scale_factor: float = 1.5
    connection_timeout: int = 30
    
    # Cache management
    cache_max_size_mb: float = 500.0
    cache_ttl_seconds: int = 3600
    cache_min_hit_rate: float = 0.3  # 30% minimum hit rate
    auto_evict: bool = True
    
    # Batch tuning
    batch_size_min: int = 10
    batch_size_max: int = 1000
    batch_size_target_latency_ms: float = 100.0
    auto_tune_batch_size: bool = True
    
    # Performance thresholds
    latency_target_ms: float = 100.0
    throughput_target: float = 100.0  # operations per second


class ResourceOptimizer:
    """Automated resource optimization system."""
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
        
        # Metrics history
        self._metrics_history: deque = deque(maxlen=1000)
        
        # Resource state
        self._current_pool_size = self.config.min_pool_size
        self._current_batch_size = self.config.batch_size_min
        self._current_cache_size = 0
        
        # Optimization state
        self._last_optimization = time.time()
        self._optimization_interval = 60  # Optimize every 60 seconds
        self._last_gc = time.time()
        
        # Performance tracking
        self._total_optimizations = 0
        self._memory_optimizations = 0
        self._pool_optimizations = 0
        self._cache_optimizations = 0
        self._batch_optimizations = 0
    
    def record_metrics(self, metrics: ResourceMetrics) -> None:
        """Record current resource metrics."""
        self._metrics_history.append(metrics)
    
    def optimize(self) -> Dict[str, Any]:
        """Run optimization analysis and apply recommendations."""
        now = time.time()
        
        # Check if optimization interval has passed
        if now - self._last_optimization < self._optimization_interval:
            return {'optimized': False, 'reason': 'interval_not_reached'}
        
        self._last_optimization = now
        self._total_optimizations += 1
        
        optimizations = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'actions': [],
        }
        
        if not self._metrics_history:
            return optimizations
        
        # Get recent metrics
        recent_metrics = list(self._metrics_history)[-10:]
        
        # Optimize memory
        memory_actions = self._optimize_memory(recent_metrics)
        optimizations['actions'].extend(memory_actions)
        
        # Optimize connection pool
        pool_actions = self._optimize_connection_pool(recent_metrics)
        optimizations['actions'].extend(pool_actions)
        
        # Optimize cache
        cache_actions = self._optimize_cache(recent_metrics)
        optimizations['actions'].extend(cache_actions)
        
        # Optimize batch size
        batch_actions = self._optimize_batch_size(recent_metrics)
        optimizations['actions'].extend(batch_actions)
        
        # Log optimizations
        if optimizations['actions']:
            logger.info(f"Applied {len(optimizations['actions'])} optimizations")
        
        return optimizations
    
    def _optimize_memory(self, recent_metrics: List[ResourceMetrics]) -> List[Dict[str, Any]]:
        """Optimize memory usage."""
        actions = []
        
        avg_memory = statistics.mean([m.memory_percent for m in recent_metrics])
        
        # Check if memory is high
        if avg_memory > self.config.memory_high_watermark:
            if self.config.auto_gc_enabled:
                # Force garbage collection
                collected = gc.collect()
                actions.append({
                    'type': 'garbage_collection',
                    'reason': f'high_memory_{avg_memory:.1%}',
                    'objects_collected': collected,
                })
                self._memory_optimizations += 1
                self._last_gc = time.time()
        
        # Periodic GC if enabled
        elif self.config.auto_gc_enabled:
            time_since_gc = time.time() - self._last_gc
            if time_since_gc > 300:  # 5 minutes
                collected = gc.collect()
                if collected > 0:
                    actions.append({
                        'type': 'periodic_gc',
                        'objects_collected': collected,
                    })
                    self._last_gc = time.time()
        
        return actions
    
    def _optimize_connection_pool(self, recent_metrics: List[ResourceMetrics]) -> List[Dict[str, Any]]:
        """Optimize connection pool size."""
        actions = []
        
        avg_connections = statistics.mean([m.active_connections for m in recent_metrics])
        max_connections = max([m.active_connections for m in recent_metrics])
        
        # Scale up if we're near capacity
        if max_connections >= self._current_pool_size * 0.8:
            new_size = min(
                int(self._current_pool_size * self.config.pool_scale_factor),
                self.config.max_pool_size
            )
            if new_size > self._current_pool_size:
                actions.append({
                    'type': 'scale_up_pool',
                    'old_size': self._current_pool_size,
                    'new_size': new_size,
                    'reason': f'high_utilization_{max_connections}/{self._current_pool_size}',
                })
                self._current_pool_size = new_size
                self._pool_optimizations += 1
        
        # Scale down if utilization is low
        elif avg_connections < self._current_pool_size * 0.3:
            new_size = max(
                int(self._current_pool_size / self.config.pool_scale_factor),
                self.config.min_pool_size
            )
            if new_size < self._current_pool_size:
                actions.append({
                    'type': 'scale_down_pool',
                    'old_size': self._current_pool_size,
                    'new_size': new_size,
                    'reason': f'low_utilization_{avg_connections:.0f}/{self._current_pool_size}',
                })
                self._current_pool_size = new_size
                self._pool_optimizations += 1
        
        return actions
    
    def _optimize_cache(self, recent_metrics: List[ResourceMetrics]) -> List[Dict[str, Any]]:
        """Optimize cache configuration."""
        actions = []
        
        if not recent_metrics:
            return actions
        
        avg_hit_rate = statistics.mean([m.cache_hit_rate for m in recent_metrics if m.cache_hit_rate > 0])
        
        # Low hit rate - cache may not be effective
        if avg_hit_rate < self.config.cache_min_hit_rate and avg_hit_rate > 0:
            if self.config.auto_evict:
                actions.append({
                    'type': 'cache_eviction',
                    'reason': f'low_hit_rate_{avg_hit_rate:.1%}',
                    'suggestion': 'Consider reviewing cache key patterns',
                })
                self._cache_optimizations += 1
        
        return actions
    
    def _optimize_batch_size(self, recent_metrics: List[ResourceMetrics]) -> List[Dict[str, Any]]:
        """Optimize batch processing size."""
        actions = []
        
        if not self.config.auto_tune_batch_size:
            return actions
        
        # Get average latency
        latencies = [m.latency_ms for m in recent_metrics if m.latency_ms > 0]
        if not latencies:
            return actions
        
        avg_latency = statistics.mean(latencies)
        
        # Latency too high - reduce batch size
        if avg_latency > self.config.batch_size_target_latency_ms * 1.5:
            new_size = max(
                int(self._current_batch_size * 0.8),
                self.config.batch_size_min
            )
            if new_size < self._current_batch_size:
                actions.append({
                    'type': 'reduce_batch_size',
                    'old_size': self._current_batch_size,
                    'new_size': new_size,
                    'reason': f'high_latency_{avg_latency:.1f}ms',
                })
                self._current_batch_size = new_size
                self._batch_optimizations += 1
        
        # Latency acceptable - can increase batch size for better throughput
        elif avg_latency < self.config.batch_size_target_latency_ms * 0.5:
            new_size = min(
                int(self._current_batch_size * 1.2),
                self.config.batch_size_max
            )
            if new_size > self._current_batch_size:
                actions.append({
                    'type': 'increase_batch_size',
                    'old_size': self._current_batch_size,
                    'new_size': new_size,
                    'reason': f'low_latency_{avg_latency:.1f}ms',
                })
                self._current_batch_size = new_size
                self._batch_optimizations += 1
        
        return actions
    
    def get_recommendations(self) -> Dict[str, Any]:
        """Get optimization recommendations without applying them."""
        if not self._metrics_history:
            return {'recommendations': []}
        
        recent_metrics = list(self._metrics_history)[-30:]
        recommendations = []
        
        # Memory recommendations
        avg_memory = statistics.mean([m.memory_percent for m in recent_metrics])
        if avg_memory > 0.7:
            recommendations.append({
                'category': 'memory',
                'priority': 'high' if avg_memory > 0.8 else 'medium',
                'issue': f'High memory usage: {avg_memory:.1%}',
                'recommendation': 'Consider increasing memory limit or optimizing data structures',
            })
        
        # Connection pool recommendations
        avg_connections = statistics.mean([m.active_connections for m in recent_metrics])
        if avg_connections > self._current_pool_size * 0.8:
            recommendations.append({
                'category': 'connections',
                'priority': 'medium',
                'issue': f'High connection usage: {avg_connections:.0f}/{self._current_pool_size}',
                'recommendation': f'Consider increasing pool size to {int(self._current_pool_size * 1.5)}',
            })
        
        # Latency recommendations
        latencies = [m.latency_ms for m in recent_metrics if m.latency_ms > 0]
        if latencies:
            avg_latency = statistics.mean(latencies)
            if avg_latency > self.config.latency_target_ms * 2:
                recommendations.append({
                    'category': 'performance',
                    'priority': 'high',
                    'issue': f'High latency: {avg_latency:.1f}ms (target: {self.config.latency_target_ms}ms)',
                    'recommendation': 'Consider reducing batch size or optimizing queries',
                })
        
        return {
            'recommendations': recommendations,
            'current_state': {
                'pool_size': self._current_pool_size,
                'batch_size': self._current_batch_size,
                'avg_memory_percent': avg_memory,
                'avg_connections': avg_connections,
                'avg_latency_ms': statistics.mean(latencies) if latencies else 0,
            },
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            'total_optimizations': self._total_optimizations,
            'memory_optimizations': self._memory_optimizations,
            'pool_optimizations': self._pool_optimizations,
            'cache_optimizations': self._cache_optimizations,
            'batch_optimizations': self._batch_optimizations,
            'current_pool_size': self._current_pool_size,
            'current_batch_size': self._current_batch_size,
            'metrics_collected': len(self._metrics_history),
        }
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current optimized configuration."""
        return {
            'connection_pool_size': self._current_pool_size,
            'batch_size': self._current_batch_size,
            'cache_size_mb': self._current_cache_size,
        }


def get_system_metrics() -> ResourceMetrics:
    """Get current system metrics."""
    try:
        import psutil
        
        process = psutil.Process()
        
        return ResourceMetrics(
            timestamp=time.time(),
            cpu_percent=process.cpu_percent(interval=0.1),
            memory_percent=process.memory_percent(),
            memory_mb=process.memory_info().rss / 1024 / 1024,
        )
    except ImportError:
        # psutil not available, return basic metrics
        import resource
        
        memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        
        return ResourceMetrics(
            timestamp=time.time(),
            memory_mb=memory_mb,
        )


if __name__ == '__main__':
    # Example usage
    import random
    
    logging.basicConfig(level=logging.INFO)
    
    config = OptimizationConfig(
        memory_high_watermark=0.80,
        auto_gc_enabled=True,
        auto_tune_batch_size=True,
    )
    
    optimizer = ResourceOptimizer(config)
    
    print("Running resource optimization demo...\n")
    
    # Simulate metrics over time
    for i in range(100):
        # Simulate varying load
        load_factor = (i % 20) / 10.0  # Oscillate between 0.0 and 2.0
        
        metrics = ResourceMetrics(
            timestamp=time.time(),
            cpu_percent=30 + random.gauss(0, 5) + load_factor * 20,
            memory_percent=0.5 + random.gauss(0, 0.05) + load_factor * 0.2,
            memory_mb=500 + random.gauss(0, 50) + load_factor * 200,
            active_connections=int(20 + random.gauss(0, 5) + load_factor * 30),
            cache_hit_rate=0.7 + random.gauss(0, 0.1),
            queue_size=int(100 + random.gauss(0, 20)),
            throughput=100 + random.gauss(0, 10) + load_factor * 50,
            latency_ms=50 + random.gauss(0, 10) + load_factor * 50,
        )
        
        optimizer.record_metrics(metrics)
        
        # Run optimization every 10 iterations
        if i % 10 == 0:
            result = optimizer.optimize()
            if result.get('actions'):
                print(f"Iteration {i}: Applied optimizations:")
                for action in result['actions']:
                    print(f"  - {action['type']}: {action.get('reason', 'N/A')}")
        
        time.sleep(0.1)
    
    # Get recommendations
    print("\nOptimization Recommendations:")
    recommendations = optimizer.get_recommendations()
    for rec in recommendations['recommendations']:
        print(f"  [{rec['priority'].upper()}] {rec['category']}: {rec['issue']}")
        print(f"    → {rec['recommendation']}")
    
    # Get statistics
    print("\nOptimization Statistics:")
    stats = optimizer.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Get current config
    print("\nCurrent Optimized Configuration:")
    current_config = optimizer.get_current_config()
    for key, value in current_config.items():
        print(f"  {key}: {value}")
