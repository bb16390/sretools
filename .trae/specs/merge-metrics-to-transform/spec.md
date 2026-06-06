
# Merge Metrics to Transform - Product Requirement Document

## Overview
- **Summary**: Merge the metrics-related scripts from worker/metrics into worker/transformer/scripts, following the existing transform script pattern.
- **Purpose**: Consolidate data processing logic into a single transform scripts directory for better code organization and reusability.
- **Target Users**: Developers working on worker module data transformation.

## Goals
- Convert existing metrics functionality to follow TransformScript abstract base class
- Place new scripts in worker/transformer/scripts/ directory
- Ensure all existing functionality is preserved
- Maintain compatibility with existing transform infrastructure (loader, registry, executor)

## Non-Goals (Out of Scope)
- Rewrite core metrics algorithm logic beyond adapting to TransformScript interface
- Add new metrics features
- Modify existing transform scripts

## Background & Context
- Currently, metrics functionality exists in worker/metrics/metric_converter.py
- Transform scripts are organized in worker/transformer/scripts/ and follow TransformScript ABC
- Metrics should be integrated into this transform scripts pattern

## Functional Requirements
- **FR-1**: Create transform script(s) for metrics functionality (metric conversion/aggregation)
- **FR-2**: New scripts must implement TransformScript ABC methods (name, transform, validate_config)
- **FR-3**: Scripts must be loadable by existing ScriptLoader

## Non-Functional Requirements
- **NFR-1**: Code must follow existing transform script style and patterns
- **NFR-2**: No breaking changes to existing transform infrastructure

## Constraints
- **Technical**: Must use existing TransformScript ABC from worker/transformer/base.py
- **Business**: Maintain existing functionality

## Assumptions
- Existing transform infrastructure (ScriptLoader, TaskRegistry, TransformExecutor) is stable
- Existing metrics logic is correct and should be preserved

## Acceptance Criteria

### AC-1: Metrics transform scripts created
- **Given**: Existing metrics code in worker/metrics/
- **When**: Metrics functionality is converted to TransformScript
- **Then**: New script exists in worker/transformer/scripts/
- **Verification**: `programmatic`

### AC-2: Scripts implement required ABC methods
- **Given**: New metrics transform script
- **When**: Checking script structure
- **Then**: Script has `name` property, `transform`, and `validate_config` methods
- **Verification**: `programmatic`

### AC-3: Script is loadable by ScriptLoader
- **Given**: New metrics script in worker/transformer/scripts/
- **When**: ScriptLoader.load_all() is called on the directory
- **Then**: Script is registered in TaskRegistry
- **Verification**: `programmatic`

## Open Questions
- [ ] Should we keep the old worker/metrics directory and code for backward compatibility, or remove it?
