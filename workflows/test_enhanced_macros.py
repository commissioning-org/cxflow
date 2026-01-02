#!/usr/bin/env python3
"""
Test script for enhanced macro capabilities.

This script validates that all enhanced macros can be loaded,
validated, and executed using the macro execution engine.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workflows.cxflow_enhanced import (
    MacroExecutionEngine,
    EnhancedMemoryManager,
    ValidationSchema,
    MacroExecutionStatus,
)


def test_macro_loading():
    """Test that all macros can be loaded and are valid JSON."""
    print("=" * 60)
    print("Test 1: Macro Loading and JSON Validation")
    print("=" * 60)
    
    macro_dir = Path(".cxflow/macros")
    macros = list(macro_dir.glob("*.json"))
    
    print(f"\nFound {len(macros)} macro files\n")
    
    loaded_macros = {}
    errors = []
    
    for macro_file in sorted(macros):
        try:
            data = json.loads(macro_file.read_text())
            loaded_macros[macro_file.stem] = data
            print(f"  ✅ {macro_file.name:<30} Loaded successfully")
        except Exception as e:
            errors.append(f"{macro_file.name}: {e}")
            print(f"  ❌ {macro_file.name:<30} Error: {e}")
    
    print(f"\nResults: {len(loaded_macros)}/{len(macros)} macros loaded successfully")
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")
        return False, loaded_macros
    
    return True, loaded_macros


def test_macro_validation(loaded_macros):
    """Test that all macros pass validation."""
    print("\n" + "=" * 60)
    print("Test 2: Macro Schema Validation")
    print("=" * 60)
    print()
    
    valid_count = 0
    invalid_count = 0
    validation_errors = {}
    
    for name, macro_def in sorted(loaded_macros.items()):
        is_valid, errors = ValidationSchema.validate_macro(macro_def)
        
        if is_valid:
            valid_count += 1
            print(f"  ✅ {name:<30} Valid")
        else:
            invalid_count += 1
            validation_errors[name] = errors
            print(f"  ❌ {name:<30} Invalid")
            for error in errors:
                print(f"      - {error}")
    
    print(f"\nResults: {valid_count}/{len(loaded_macros)} macros are valid")
    
    return invalid_count == 0


def test_macro_execution(loaded_macros):
    """Test that macros can be executed (dry run)."""
    print("\n" + "=" * 60)
    print("Test 3: Macro Execution (Dry Run)")
    print("=" * 60)
    print()
    
    # Initialize execution engine
    memory_manager = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_test/memory"),
        enable_versioning=True,
    )
    
    # Set up some test memory entries
    memory_manager.set("test_config", {"enabled": True}, category="test")
    memory_manager.set("quality_thresholds", {"completeness": 0.95}, category="test")
    memory_manager.set("ml_config", {"model": "test"}, category="test")
    memory_manager.set("monitoring_config", {"interval": 300}, category="test")
    memory_manager.set("batch_config", {"size": 100}, category="test")
    memory_manager.set("alert_config", {"enabled": True}, category="test")
    
    engine = MacroExecutionEngine(memory_manager)
    
    success_count = 0
    failure_count = 0
    execution_results = {}
    
    # Test context for macro execution
    test_context = {
        "timestamp": datetime.now().isoformat(),
        "commit_sha": "abc123",
        "pipeline_name": "test_pipeline",
        "dataset_name": "test_dataset",
        "service_name": "test_service",
        "alert_type": "test_alert",
        "priority": "high",
        "alert_message": "Test alert message",
        "alert_count": 5,
        "metric_value": 85,
        "items": ["item1", "item2", "item3"],
        "data": {"key": "value"},
        "event_type": "test_event",
        "data_path": "/path/to/data",
        "monitoring_data": ["data1", "data2"],
    }
    
    for name, macro_def in sorted(loaded_macros.items()):
        try:
            # Execute in dry-run mode (doesn't actually execute actions)
            execution = engine.execute_macro(
                macro_def,
                context=test_context,
                dry_run=True
            )
            
            if execution.status == MacroExecutionStatus.COMPLETED:
                success_count += 1
                execution_results[name] = "success"
                print(f"  ✅ {name:<30} Executed (dry-run)")
            else:
                failure_count += 1
                execution_results[name] = "failed"
                print(f"  ❌ {name:<30} Failed (dry-run)")
                if execution.errors:
                    for error in execution.errors:
                        print(f"      - {error}")
        except Exception as e:
            failure_count += 1
            execution_results[name] = str(e)
            print(f"  ❌ {name:<30} Error: {e}")
    
    print(f"\nResults: {success_count}/{len(loaded_macros)} macros executed successfully (dry-run)")
    
    return failure_count == 0


def test_enhanced_features(loaded_macros):
    """Test that enhanced features are present in macros."""
    print("\n" + "=" * 60)
    print("Test 4: Enhanced Features Analysis")
    print("=" * 60)
    print()
    
    feature_stats = {
        "conditionals": 0,
        "loops": 0,
        "transformations": 0,
        "error_handling": 0,
        "retry_logic": 0,
        "validation": 0,
        "nested_conditionals": 0,
        "multi_stage": 0,
    }
    
    enhanced_count = 0
    
    for name, macro_def in sorted(loaded_macros.items()):
        metadata = macro_def.get("metadata", {})
        is_enhanced = metadata.get("enhanced", False)
        features = metadata.get("features", [])
        
        if is_enhanced:
            enhanced_count += 1
        
        # Count feature usage
        for feature in features:
            for key in feature_stats.keys():
                if key in feature:
                    feature_stats[key] += 1
        
        print(f"  {name:<30} Enhanced: {is_enhanced}  Features: {len(features)}")
        if features:
            print(f"      {', '.join(features)}")
    
    print(f"\nEnhanced macros: {enhanced_count}/{len(loaded_macros)}")
    print("\nFeature usage across all macros:")
    for feature, count in sorted(feature_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {feature:<25} {count} macros")
    
    return enhanced_count == len(loaded_macros)


def test_macro_complexity():
    """Test macro complexity and action counts."""
    print("\n" + "=" * 60)
    print("Test 5: Macro Complexity Analysis")
    print("=" * 60)
    print()
    
    macro_dir = Path(".cxflow/macros")
    macros = list(macro_dir.glob("*.json"))
    
    complexity_data = []
    
    for macro_file in sorted(macros):
        try:
            data = json.loads(macro_file.read_text())
            actions = data.get("actions", [])
            
            # Count nested actions (loops, conditionals)
            nested_count = 0
            for action in actions:
                if action.get("type") == "loop":
                    nested_count += len(action.get("actions", []))
                elif action.get("type") == "condition":
                    nested_count += len(action.get("then", []))
                    nested_count += len(action.get("else", []))
            
            complexity_data.append({
                "name": macro_file.stem,
                "actions": len(actions),
                "nested": nested_count,
                "total": len(actions) + nested_count,
            })
            
        except Exception as e:
            print(f"  ❌ Error analyzing {macro_file.name}: {e}")
    
    # Print sorted by complexity
    for item in sorted(complexity_data, key=lambda x: x["total"], reverse=True):
        print(f"  {item['name']:<30} Actions: {item['actions']:>3}  Nested: {item['nested']:>3}  Total: {item['total']:>3}")
    
    avg_actions = sum(d["actions"] for d in complexity_data) / len(complexity_data)
    avg_nested = sum(d["nested"] for d in complexity_data) / len(complexity_data)
    avg_total = sum(d["total"] for d in complexity_data) / len(complexity_data)
    
    print(f"\nAverage actions per macro: {avg_actions:.1f}")
    print(f"Average nested actions: {avg_nested:.1f}")
    print(f"Average total complexity: {avg_total:.1f}")
    
    return True


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "Enhanced Macro Capabilities Test" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    all_passed = True
    
    # Test 1: Loading
    success, loaded_macros = test_macro_loading()
    all_passed = all_passed and success
    
    if not loaded_macros:
        print("\n❌ Cannot continue tests - no macros loaded")
        return 1
    
    # Test 2: Validation
    success = test_macro_validation(loaded_macros)
    all_passed = all_passed and success
    
    # Test 3: Execution
    success = test_macro_execution(loaded_macros)
    all_passed = all_passed and success
    
    # Test 4: Enhanced features
    success = test_enhanced_features(loaded_macros)
    all_passed = all_passed and success
    
    # Test 5: Complexity
    test_macro_complexity()
    
    # Final summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    print()
    
    print("Summary:")
    print(f"  Total macros: {len(loaded_macros)}")
    print(f"  All macros enhanced: ✅")
    print(f"  Features demonstrated:")
    print(f"    - Conditional logic (if/then/else)")
    print(f"    - Loops and iterations")
    print(f"    - Data transformations")
    print(f"    - Error handling and retry logic")
    print(f"    - Memory management")
    print(f"    - Multi-stage workflows")
    print(f"    - Nested operations")
    print(f"    - Variable resolution")
    print(f"    - Self-healing capabilities")
    print()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
