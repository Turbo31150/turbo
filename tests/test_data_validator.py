"""Tests for src/data_validator.py — Schema-based data validation engine.

Covers: Severity, ValidationError, ValidationResult (to_dict, error_count,
warning_count), FieldSchema, TYPE_MAP, DataValidator (register/unregister/get/list
schemas, validate, validate_inline, _validate_fields — required, type, range,
length, regex, choices, custom_validator, nested_schema), get_history, get_stats,
data_validator singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_validator import (
    Severity, ValidationError, ValidationResult, FieldSchema,
    TYPE_MAP, DataValidator, data_validator,
)


# ===========================================================================
# Enums & Dataclasses
# ===========================================================================

class TestSeverity:
    def test_values(self):
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"


class TestValidationError:
    def test_defaults(self):
        e = ValidationError(field="name", message="required")
        assert e.severity == Severity.ERROR
        assert e.value is None


class TestValidationResult:
    def test_defaults(self):
        r = ValidationResult(valid=True)
        assert r.errors == []
        assert r.warnings == []
        assert r.error_count == 0
        assert r.warning_count == 0
        assert r.schema_name == ""
        assert r.timestamp > 0

    def test_error_count(self):
        r = ValidationResult(valid=False, errors=[
            ValidationError("a", "err1"),
            ValidationError("b", "err2"),
        ])
        assert r.error_count == 2

    def test_to_dict(self):
        r = ValidationResult(
            valid=False, schema_name="test",
            errors=[ValidationError("name", "required")],
            duration_ms=1.5,
        )
        d = r.to_dict()
        assert d["valid"] is False
        assert d["schema"] == "test"
        assert d["error_count"] == 1
        assert d["warning_count"] == 0
        assert d["duration_ms"] == 1.5
        assert d["errors"][0]["field"] == "name"
        assert d["errors"][0]["severity"] == "error"


class TestFieldSchema:
    def test_defaults(self):
        f = FieldSchema(name="age")
        assert f.field_type == "any"
        assert f.required is False
        assert f.min_value is None
        assert f.pattern is None
        assert f.choices is None
        assert f.nested_schema is None


class TestTypeMap:
    def test_str(self):
        assert TYPE_MAP["str"] is str

    def test_float_includes_int(self):
        assert isinstance(42, TYPE_MAP["float"])
        assert isinstance(3.14, TYPE_MAP["float"])

    def test_bool(self):
        assert TYPE_MAP["bool"] is bool


# ===========================================================================
# DataValidator — Schema Management
# ===========================================================================

class TestSchemaManagement:
    def test_register_and_get(self):
        dv = DataValidator()
        fields = [FieldSchema(name="name", field_type="str", required=True)]
        dv.register_schema("user", fields)
        assert dv.get_schema("user") is not None
        assert len(dv.get_schema("user")) == 1

    def test_get_missing(self):
        dv = DataValidator()
        assert dv.get_schema("nope") is None

    def test_unregister(self):
        dv = DataValidator()
        dv.register_schema("x", [FieldSchema(name="a")])
        assert dv.unregister_schema("x") is True
        assert dv.unregister_schema("x") is False

    def test_list_schemas(self):
        dv = DataValidator()
        dv.register_schema("user", [
            FieldSchema(name="name", required=True),
            FieldSchema(name="age"),
        ])
        dv.register_schema("item", [FieldSchema(name="id", required=True)])
        result = dv.list_schemas()
        assert len(result) == 2
        user_schema = [s for s in result if s["name"] == "user"][0]
        assert user_schema["fields"] == 2
        assert user_schema["required"] == 1

    def test_list_empty(self):
        dv = DataValidator()
        assert dv.list_schemas() == []


# ===========================================================================
# DataValidator — validate (schema not found)
# ===========================================================================

class TestValidateSchemaNotFound:
    def test_unknown_schema(self):
        dv = DataValidator()
        result = dv.validate({"a": 1}, "nonexistent")
        assert result.valid is False
        assert result.error_count == 1
        assert "not found" in result.errors[0].message


# ===========================================================================
# DataValidator — _validate_fields: required
# ===========================================================================

class TestValidateRequired:
    def test_required_present(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", required=True)])
        r = dv.validate({"name": "Alice"}, "t")
        assert r.valid is True

    def test_required_missing(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", required=True)])
        r = dv.validate({}, "t")
        assert r.valid is False
        assert "required" in r.errors[0].message

    def test_optional_missing(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="age")])
        r = dv.validate({}, "t")
        assert r.valid is True


# ===========================================================================
# DataValidator — _validate_fields: type
# ===========================================================================

class TestValidateType:
    def test_correct_type(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", field_type="str")])
        r = dv.validate({"name": "Alice"}, "t")
        assert r.valid is True

    def test_wrong_type(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", field_type="str")])
        r = dv.validate({"name": 123}, "t")
        assert r.valid is False
        assert "Expected type" in r.errors[0].message

    def test_any_type(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="data", field_type="any")])
        r = dv.validate({"data": [1, 2, 3]}, "t")
        assert r.valid is True

    def test_int_valid_for_float(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="val", field_type="float")])
        r = dv.validate({"val": 42}, "t")
        assert r.valid is True


# ===========================================================================
# DataValidator — _validate_fields: range
# ===========================================================================

class TestValidateRange:
    def test_within_range(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="age", field_type="int", min_value=0, max_value=150)])
        r = dv.validate({"age": 25}, "t")
        assert r.valid is True

    def test_below_min(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="age", field_type="int", min_value=0)])
        r = dv.validate({"age": -5}, "t")
        assert r.valid is False
        assert "below minimum" in r.errors[0].message

    def test_above_max(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="age", field_type="int", max_value=100)])
        r = dv.validate({"age": 200}, "t")
        assert r.valid is False
        assert "above maximum" in r.errors[0].message


# ===========================================================================
# DataValidator — _validate_fields: length
# ===========================================================================

class TestValidateLength:
    def test_string_ok(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", field_type="str", min_length=2, max_length=10)])
        r = dv.validate({"name": "Alice"}, "t")
        assert r.valid is True

    def test_string_too_short(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", field_type="str", min_length=5)])
        r = dv.validate({"name": "Al"}, "t")
        assert r.valid is False
        assert "below minimum" in r.errors[0].message

    def test_string_too_long(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="name", field_type="str", max_length=3)])
        r = dv.validate({"name": "Alice"}, "t")
        assert r.valid is False
        assert "above maximum" in r.errors[0].message

    def test_list_length(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="tags", field_type="list", min_length=1)])
        r = dv.validate({"tags": []}, "t")
        assert r.valid is False


# ===========================================================================
# DataValidator — _validate_fields: regex
# ===========================================================================

class TestValidateRegex:
    def test_matches(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="email", field_type="str", pattern=r"^[\w.]+@[\w.]+$")])
        r = dv.validate({"email": "test@example.com"}, "t")
        assert r.valid is True

    def test_no_match(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="email", field_type="str", pattern=r"^[\w.]+@[\w.]+$")])
        r = dv.validate({"email": "not-an-email"}, "t")
        assert r.valid is False
        assert "pattern" in r.errors[0].message


# ===========================================================================
# DataValidator — _validate_fields: choices
# ===========================================================================

class TestValidateChoices:
    def test_valid_choice(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="color", choices=["red", "green", "blue"])])
        r = dv.validate({"color": "red"}, "t")
        assert r.valid is True

    def test_invalid_choice(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="color", choices=["red", "green", "blue"])])
        r = dv.validate({"color": "yellow"}, "t")
        assert r.valid is False
        assert "one of" in r.errors[0].message


# ===========================================================================
# DataValidator — _validate_fields: custom_validator
# ===========================================================================

class TestValidateCustom:
    def test_returns_true(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="x", custom_validator=lambda v: True)])
        r = dv.validate({"x": 42}, "t")
        assert r.valid is True

    def test_returns_false(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="x", custom_validator=lambda v: False)])
        r = dv.validate({"x": 42}, "t")
        assert r.valid is False
        assert "Custom validation failed" in r.errors[0].message

    def test_returns_string(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="x", custom_validator=lambda v: "too big")])
        r = dv.validate({"x": 999}, "t")
        assert r.valid is False
        assert "too big" in r.errors[0].message

    def test_raises_exception(self):
        dv = DataValidator()
        def bad_validator(v):
            raise ValueError("boom")
        dv.register_schema("t", [FieldSchema(name="x", custom_validator=bad_validator)])
        r = dv.validate({"x": 1}, "t")
        assert r.valid is False
        assert "Validator error" in r.errors[0].message


# ===========================================================================
# DataValidator — _validate_fields: nested_schema
# ===========================================================================

class TestValidateNested:
    def test_nested_valid(self):
        dv = DataValidator()
        dv.register_schema("address", [
            FieldSchema(name="city", field_type="str", required=True),
        ])
        dv.register_schema("user", [
            FieldSchema(name="addr", nested_schema="address"),
        ])
        r = dv.validate({"addr": {"city": "Paris"}}, "user")
        assert r.valid is True

    def test_nested_invalid(self):
        dv = DataValidator()
        dv.register_schema("address", [
            FieldSchema(name="city", field_type="str", required=True),
        ])
        dv.register_schema("user", [
            FieldSchema(name="addr", nested_schema="address"),
        ])
        r = dv.validate({"addr": {}}, "user")
        assert r.valid is False
        assert any("addr.city" in e.field for e in r.errors)


# ===========================================================================
# DataValidator — validate_inline
# ===========================================================================

class TestValidateInline:
    def test_inline(self):
        dv = DataValidator()
        fields = [FieldSchema(name="x", field_type="int", required=True)]
        r = dv.validate_inline({"x": 42}, fields)
        assert r.valid is True
        assert r.schema_name == "inline"

    def test_inline_custom_name(self):
        dv = DataValidator()
        fields = [FieldSchema(name="x")]
        r = dv.validate_inline({"x": 1}, fields, schema_name="custom")
        assert r.schema_name == "custom"


# ===========================================================================
# DataValidator — get_history / get_stats
# ===========================================================================

class TestHistoryAndStats:
    def test_history_empty(self):
        dv = DataValidator()
        assert dv.get_history() == []

    def test_history_with_data(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="x")])
        dv.validate({"x": 1}, "t")
        dv.validate({"x": 2}, "t")
        h = dv.get_history()
        assert len(h) == 2

    def test_history_limit(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="x")])
        for i in range(10):
            dv.validate({"x": i}, "t")
        h = dv.get_history(limit=3)
        assert len(h) == 3

    def test_stats_empty(self):
        dv = DataValidator()
        stats = dv.get_stats()
        assert stats["total_schemas"] == 0
        assert stats["total_validations"] == 0
        assert stats["pass_rate"] == 0.0

    def test_stats_with_data(self):
        dv = DataValidator()
        dv.register_schema("t", [FieldSchema(name="x", field_type="int", required=True)])
        dv.validate({"x": 1}, "t")  # pass
        dv.validate({}, "t")  # fail
        stats = dv.get_stats()
        assert stats["total_schemas"] == 1
        assert stats["total_validations"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["pass_rate"] == 50.0
        assert stats["total_errors"] >= 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert data_validator is not None
        assert isinstance(data_validator, DataValidator)
