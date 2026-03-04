"""Data Validator — Schema-based data validation engine.

Validate dictionaries against schemas with type checking, ranges,
regex patterns, required fields, custom validators, and nested objects.
Supports reusable schema definitions and validation reports.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("jarvis.data_validator")


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """A single validation error."""
    field: str
    message: str
    severity: Severity = Severity.ERROR
    value: Any = None


@dataclass
class ValidationResult:
    """Result of a validation run."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    schema_name: str = ""
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [{"field": e.field, "message": e.message, "severity": e.severity.value} for e in self.errors],
            "warnings": [{"field": w.field, "message": w.message, "severity": w.severity.value} for w in self.warnings],
            "schema": self.schema_name,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "duration_ms": self.duration_ms,
        }


@dataclass
class FieldSchema:
    """Schema for a single field."""
    name: str
    field_type: str = "any"  # str, int, float, bool, list, dict, any
    required: bool = False
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None  # regex
    choices: list[Any] | None = None
    default: Any = None
    custom_validator: Callable[[Any], bool | str] | None = None
    nested_schema: str | None = None  # reference to another schema


TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "str": str,
    "int": int,
    "float": (int, float),
    "bool": bool,
    "list": list,
    "dict": dict,
}


class DataValidator:
    """Schema-based data validation engine."""

    def __init__(self) -> None:
        self._schemas: dict[str, list[FieldSchema]] = {}
        self._history: list[ValidationResult] = []

    # ── Schema Management ───────────────────────────────────────────

    def register_schema(self, name: str, fields: list[FieldSchema]) -> None:
        """Register a named schema."""
        self._schemas[name] = fields

    def unregister_schema(self, name: str) -> bool:
        """Remove a schema."""
        if name in self._schemas:
            del self._schemas[name]
            return True
        return False

    def get_schema(self, name: str) -> list[FieldSchema] | None:
        """Get a schema by name."""
        return self._schemas.get(name)

    def list_schemas(self) -> list[dict[str, Any]]:
        """List all registered schemas."""
        return [
            {"name": name, "fields": len(fields), "required": sum(1 for f in fields if f.required)}
            for name, fields in self._schemas.items()
        ]

    # ── Validation ──────────────────────────────────────────────────

    def validate(self, data: dict[str, Any], schema_name: str) -> ValidationResult:
        """Validate data against a named schema."""
        fields = self._schemas.get(schema_name)
        if not fields:
            result = ValidationResult(
                valid=False, schema_name=schema_name,
                errors=[ValidationError(field="__schema__", message=f"Schema '{schema_name}' not found")],
            )
            self._history.append(result)
            return result
        return self._validate_fields(data, fields, schema_name)

    def validate_inline(self, data: dict[str, Any], fields: list[FieldSchema], schema_name: str = "inline") -> ValidationResult:
        """Validate data against inline field schemas (not registered)."""
        return self._validate_fields(data, fields, schema_name)

    def _validate_fields(self, data: dict[str, Any], fields: list[FieldSchema], schema_name: str) -> ValidationResult:
        """Core validation logic."""
        start = time.time()
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []

        for fs in fields:
            value = data.get(fs.name)

            # Required check
            if fs.required and (value is None and fs.name not in data):
                errors.append(ValidationError(field=fs.name, message="Field is required"))
                continue

            if value is None:
                continue

            # Type check
            if fs.field_type != "any":
                expected = TYPE_MAP.get(fs.field_type)
                if expected and not isinstance(value, expected):
                    errors.append(ValidationError(
                        field=fs.name,
                        message=f"Expected type {fs.field_type}, got {type(value).__name__}",
                        value=value,
                    ))
                    continue

            # Range check (numeric)
            if isinstance(value, (int, float)):
                if fs.min_value is not None and value < fs.min_value:
                    errors.append(ValidationError(
                        field=fs.name, message=f"Value {value} below minimum {fs.min_value}", value=value,
                    ))
                if fs.max_value is not None and value > fs.max_value:
                    errors.append(ValidationError(
                        field=fs.name, message=f"Value {value} above maximum {fs.max_value}", value=value,
                    ))

            # Length check (string/list)
            if isinstance(value, (str, list)):
                if fs.min_length is not None and len(value) < fs.min_length:
                    errors.append(ValidationError(
                        field=fs.name, message=f"Length {len(value)} below minimum {fs.min_length}", value=value,
                    ))
                if fs.max_length is not None and len(value) > fs.max_length:
                    errors.append(ValidationError(
                        field=fs.name, message=f"Length {len(value)} above maximum {fs.max_length}", value=value,
                    ))

            # Regex check
            if fs.pattern and isinstance(value, str):
                if not re.match(fs.pattern, value):
                    errors.append(ValidationError(
                        field=fs.name, message=f"Value does not match pattern {fs.pattern}", value=value,
                    ))

            # Choices check
            if fs.choices is not None and value not in fs.choices:
                errors.append(ValidationError(
                    field=fs.name, message=f"Value must be one of {fs.choices}", value=value,
                ))

            # Custom validator
            if fs.custom_validator:
                try:
                    result = fs.custom_validator(value)
                    if result is False:
                        errors.append(ValidationError(
                            field=fs.name, message="Custom validation failed", value=value,
                        ))
                    elif isinstance(result, str):
                        errors.append(ValidationError(
                            field=fs.name, message=result, value=value,
                        ))
                except Exception as e:
                    errors.append(ValidationError(
                        field=fs.name, message=f"Validator error: {e}", value=value,
                    ))

            # Nested schema
            if fs.nested_schema and isinstance(value, dict):
                nested = self._schemas.get(fs.nested_schema)
                if nested:
                    nested_result = self._validate_fields(value, nested, fs.nested_schema)
                    for err in nested_result.errors:
                        errors.append(ValidationError(
                            field=f"{fs.name}.{err.field}", message=err.message, value=err.value,
                        ))

        duration = (time.time() - start) * 1000
        vr = ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            schema_name=schema_name,
            duration_ms=round(duration, 3),
        )
        self._history.append(vr)
        return vr

    # ── History & Stats ─────────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get validation history."""
        return [r.to_dict() for r in self._history[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics."""
        total = len(self._history)
        passed = sum(1 for r in self._history if r.valid)
        return {
            "total_schemas": len(self._schemas),
            "total_validations": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0.0,
            "total_errors": sum(r.error_count for r in self._history),
        }


# ── Singleton ───────────────────────────────────────────────────────
data_validator = DataValidator()
