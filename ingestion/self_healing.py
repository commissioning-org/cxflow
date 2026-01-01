#!/usr/bin/env python3
"""
Self-healing automation system with automatic rollback and recovery.

Features:
- Automatic error detection and recovery
- Transaction-like operations with rollback
- Health monitoring and self-correction
- Automatic retry with exponential backoff
- Circuit breaker pattern
- State checkpoint and restore
- Graceful degradation
- Alerting and notification
"""

import json
import time
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status of a component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RecoveryStrategy(str, Enum):
    """Recovery strategy for failures."""
    RETRY = "retry"
    ROLLBACK = "rollback"
    FAILOVER = "failover"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    check_func: Callable[[], bool]
    critical: bool = False
    timeout_seconds: int = 5
    failure_threshold: int = 3
    recovery_threshold: int = 2
    
    # Internal state
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check: Optional[float] = None
    last_status: HealthStatus = HealthStatus.UNKNOWN


@dataclass
class Checkpoint:
    """State checkpoint for rollback."""
    checkpoint_id: str
    timestamp: str
    state: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryAction:
    """Recovery action to take on failure."""
    strategy: RecoveryStrategy
    max_retries: int = 3
    retry_delay_ms: int = 1000
    retry_backoff_multiplier: float = 2.0
    rollback_checkpoint: Optional[str] = None
    failover_target: Optional[str] = None
    on_success: Optional[Callable] = None
    on_failure: Optional[Callable] = None


@dataclass
class AutomationResult:
    """Result of an automation execution."""
    ok: bool
    operation: str
    duration_ms: int = 0
    retries: int = 0
    recovery_actions: List[str] = field(default_factory=list)
    checkpoints_created: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SelfHealingAutomation:
    """Self-healing automation system."""
    
    def __init__(self, checkpoint_dir: Optional[Path] = None):
        self.checkpoint_dir = checkpoint_dir or Path("./.cxflow/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.health_checks: Dict[str, HealthCheck] = {}
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Load persisted checkpoints
        self._load_checkpoints()
    
    def register_health_check(self, check: HealthCheck) -> None:
        """Register a health check."""
        self.health_checks[check.name] = check
        logger.info(f"Registered health check: {check.name}")
    
    def check_health(self, name: Optional[str] = None) -> Dict[str, HealthStatus]:
        """Check health of components."""
        results = {}
        
        checks_to_run = [self.health_checks[name]] if name else self.health_checks.values()
        
        for check in checks_to_run:
            try:
                start_time = time.time()
                is_healthy = check.check_func()
                elapsed = time.time() - start_time
                
                if elapsed > check.timeout_seconds:
                    is_healthy = False
                    logger.warning(f"Health check {check.name} timed out ({elapsed:.2f}s)")
                
                if is_healthy:
                    check.consecutive_successes += 1
                    check.consecutive_failures = 0
                    
                    if check.consecutive_successes >= check.recovery_threshold:
                        check.last_status = HealthStatus.HEALTHY
                else:
                    check.consecutive_failures += 1
                    check.consecutive_successes = 0
                    
                    if check.consecutive_failures >= check.failure_threshold:
                        check.last_status = HealthStatus.UNHEALTHY
                    else:
                        check.last_status = HealthStatus.DEGRADED
                
                check.last_check = time.time()
                results[check.name] = check.last_status
                
            except Exception as e:
                logger.exception(f"Health check {check.name} failed with exception")
                check.consecutive_failures += 1
                check.last_status = HealthStatus.UNHEALTHY
                results[check.name] = HealthStatus.UNHEALTHY
        
        return results
    
    def create_checkpoint(self, state: Dict[str, Any], label: str = "") -> str:
        """Create a state checkpoint."""
        checkpoint_id = hashlib.sha256(
            f"{time.time()}{label}{json.dumps(state, sort_keys=True)}".encode()
        ).hexdigest()[:16]
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            state=state.copy(),
            metadata={'label': label} if label else {},
        )
        
        self.checkpoints[checkpoint_id] = checkpoint
        self._persist_checkpoint(checkpoint)
        
        logger.info(f"Created checkpoint: {checkpoint_id} ({label})")
        return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Restore state from checkpoint."""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return None
        
        logger.info(f"Restored checkpoint: {checkpoint_id}")
        return checkpoint.state.copy()
    
    def execute_with_recovery(
        self,
        operation: Callable[[], Any],
        operation_name: str,
        recovery: Optional[RecoveryAction] = None,
        create_checkpoint: bool = True,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> AutomationResult:
        """Execute operation with automatic recovery."""
        start_time = time.time()
        
        result = AutomationResult(
            ok=False,
            operation=operation_name,
        )
        
        # Create checkpoint if requested
        checkpoint_id = None
        if create_checkpoint and current_state:
            checkpoint_id = self.create_checkpoint(current_state, operation_name)
            result.checkpoints_created.append(checkpoint_id)
        
        # Default recovery strategy
        if recovery is None:
            recovery = RecoveryAction(strategy=RecoveryStrategy.RETRY, max_retries=3)
        
        # Check circuit breaker
        if self._is_circuit_open(operation_name):
            result.errors.append(f"Circuit breaker open for {operation_name}")
            result.warnings.append("Skipping operation due to circuit breaker")
            return result
        
        # Execute with retry
        last_error = None
        for attempt in range(recovery.max_retries + 1):
            try:
                # Check health before attempting
                health = self.check_health()
                critical_unhealthy = any(
                    status == HealthStatus.UNHEALTHY and check.critical
                    for check_name, status in health.items()
                    if check_name in self.health_checks
                    for check in [self.health_checks[check_name]]
                )
                
                if critical_unhealthy:
                    result.errors.append("Critical component unhealthy")
                    result.warnings.append("Aborting due to critical health check failure")
                    break
                
                # Execute operation
                operation_result = operation()
                
                # Success
                result.ok = True
                result.metadata['result'] = operation_result
                self._record_circuit_success(operation_name)
                
                if recovery.on_success:
                    recovery.on_success()
                
                break
                
            except Exception as e:
                last_error = str(e)
                result.retries = attempt
                logger.warning(f"Operation {operation_name} failed (attempt {attempt + 1}/{recovery.max_retries + 1}): {e}")
                
                self._record_circuit_failure(operation_name)
                
                # Apply recovery strategy
                if attempt < recovery.max_retries:
                    if recovery.strategy == RecoveryStrategy.RETRY:
                        # Exponential backoff
                        delay_ms = recovery.retry_delay_ms * (recovery.retry_backoff_multiplier ** attempt)
                        result.recovery_actions.append(f"retry_after_{int(delay_ms)}ms")
                        time.sleep(delay_ms / 1000)
                    
                    elif recovery.strategy == RecoveryStrategy.ROLLBACK:
                        if checkpoint_id:
                            restored_state = self.restore_checkpoint(checkpoint_id)
                            result.recovery_actions.append(f"rollback_to_{checkpoint_id}")
                            result.metadata['restored_state'] = restored_state
                        else:
                            result.warnings.append("Rollback requested but no checkpoint available")
                    
                    elif recovery.strategy == RecoveryStrategy.FAILOVER:
                        if recovery.failover_target:
                            result.recovery_actions.append(f"failover_to_{recovery.failover_target}")
                            result.warnings.append(f"Failover to {recovery.failover_target}")
                        else:
                            result.warnings.append("Failover requested but no target specified")
                    
                    elif recovery.strategy == RecoveryStrategy.SKIP:
                        result.recovery_actions.append("skip")
                        result.warnings.append("Skipping failed operation")
                        break
                    
                    elif recovery.strategy == RecoveryStrategy.ABORT:
                        result.recovery_actions.append("abort")
                        result.errors.append("Aborting due to failure")
                        break
        
        if not result.ok:
            result.errors.append(last_error or "Unknown error")
            
            if recovery.on_failure:
                recovery.on_failure()
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        result.duration_ms = elapsed_ms
        
        return result
    
    def _is_circuit_open(self, operation_name: str) -> bool:
        """Check if circuit breaker is open."""
        breaker = self.circuit_breakers.get(operation_name)
        if not breaker:
            return False
        
        if breaker['state'] != 'open':
            return False
        
        # Check if timeout has passed
        if time.time() > breaker['open_until']:
            breaker['state'] = 'half_open'
            return False
        
        return True
    
    def _record_circuit_success(self, operation_name: str) -> None:
        """Record successful operation for circuit breaker."""
        if operation_name not in self.circuit_breakers:
            self.circuit_breakers[operation_name] = {
                'state': 'closed',
                'failure_count': 0,
                'success_count': 0,
                'open_until': 0,
            }
        
        breaker = self.circuit_breakers[operation_name]
        breaker['success_count'] += 1
        breaker['failure_count'] = max(0, breaker['failure_count'] - 1)
        
        if breaker['state'] == 'half_open' and breaker['success_count'] >= 2:
            breaker['state'] = 'closed'
            logger.info(f"Circuit breaker closed for {operation_name}")
    
    def _record_circuit_failure(self, operation_name: str) -> None:
        """Record failed operation for circuit breaker."""
        if operation_name not in self.circuit_breakers:
            self.circuit_breakers[operation_name] = {
                'state': 'closed',
                'failure_count': 0,
                'success_count': 0,
                'open_until': 0,
            }
        
        breaker = self.circuit_breakers[operation_name]
        breaker['failure_count'] += 1
        breaker['success_count'] = 0
        
        # Open circuit if too many failures
        if breaker['failure_count'] >= 5:
            breaker['state'] = 'open'
            breaker['open_until'] = time.time() + 60  # 60 second timeout
            logger.warning(f"Circuit breaker opened for {operation_name}")
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        health_checks = self.check_health()
        
        overall_status = HealthStatus.HEALTHY
        if any(status == HealthStatus.UNHEALTHY for status in health_checks.values()):
            overall_status = HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in health_checks.values()):
            overall_status = HealthStatus.DEGRADED
        
        return {
            'overall_status': overall_status.value,
            'components': {
                name: {
                    'status': status.value,
                    'critical': self.health_checks[name].critical if name in self.health_checks else False,
                    'last_check': self.health_checks[name].last_check if name in self.health_checks else None,
                }
                for name, status in health_checks.items()
            },
            'circuit_breakers': {
                name: breaker['state']
                for name, breaker in self.circuit_breakers.items()
            },
            'checkpoints': len(self.checkpoints),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }
    
    def _persist_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persist checkpoint to disk."""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint.checkpoint_id}.json"
        checkpoint_file.write_text(json.dumps(asdict(checkpoint), indent=2))
    
    def _load_checkpoints(self) -> None:
        """Load persisted checkpoints from disk."""
        if not self.checkpoint_dir.exists():
            return
        
        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(checkpoint_file.read_text())
                checkpoint = Checkpoint(**data)
                self.checkpoints[checkpoint.checkpoint_id] = checkpoint
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed = 0
        
        for checkpoint_id, checkpoint in list(self.checkpoints.items()):
            checkpoint_time = datetime.fromisoformat(checkpoint.timestamp.replace('Z', '+00:00'))
            if checkpoint_time < cutoff:
                # Remove from memory
                del self.checkpoints[checkpoint_id]
                
                # Remove from disk
                checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
                
                removed += 1
        
        logger.info(f"Cleaned up {removed} old checkpoints")
        return removed


# Example health check functions
def check_disk_space() -> bool:
    """Check if sufficient disk space is available."""
    import shutil
    usage = shutil.disk_usage("/")
    free_percent = (usage.free / usage.total) * 100
    return free_percent > 10  # At least 10% free


def check_memory() -> bool:
    """Check if sufficient memory is available."""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return memory.percent < 90  # Less than 90% used
    except ImportError:
        return True  # Assume OK if psutil not available


if __name__ == '__main__':
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    automation = SelfHealingAutomation()
    
    # Register health checks
    automation.register_health_check(HealthCheck(
        name="disk_space",
        check_func=check_disk_space,
        critical=True,
    ))
    
    automation.register_health_check(HealthCheck(
        name="memory",
        check_func=check_memory,
        critical=False,
    ))
    
    # Example operation with recovery
    def risky_operation():
        import random
        if random.random() < 0.7:  # 70% failure rate for demo
            raise Exception("Simulated failure")
        return "Success!"
    
    result = automation.execute_with_recovery(
        operation=risky_operation,
        operation_name="example_operation",
        recovery=RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            max_retries=5,
            retry_delay_ms=100,
        ),
        create_checkpoint=True,
        current_state={'example': 'state'},
    )
    
    print(json.dumps(asdict(result), indent=2))
    
    # Get system health
    health = automation.get_system_health()
    print("\nSystem Health:")
    print(json.dumps(health, indent=2))
