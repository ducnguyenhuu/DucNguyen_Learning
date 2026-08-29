"""
tests/test_calculator.py — Unit tests for the calculator module.
"""

import pytest
from calculator import add, subtract, multiply, divide, calculate


# ─── add ──────────────────────────────────────────────────────────────────────

class TestAdd:
    def test_positive_numbers(self):
        assert add(2, 3) == 5

    def test_negative_numbers(self):
        assert add(-2, -3) == -5

    def test_mixed_sign(self):
        assert add(-2, 3) == 1

    def test_floats(self):
        assert add(0.1, 0.2) == pytest.approx(0.3)

    def test_zero(self):
        assert add(0, 5) == 5
        assert add(5, 0) == 5
        assert add(0, 0) == 0

    def test_large_numbers(self):
        assert add(1_000_000, 2_000_000) == 3_000_000


# ─── subtract ─────────────────────────────────────────────────────────────────

class TestSubtract:
    def test_positive_numbers(self):
        assert subtract(5, 3) == 2

    def test_negative_result(self):
        assert subtract(3, 5) == -2

    def test_negative_numbers(self):
        assert subtract(-2, -3) == 1

    def test_floats(self):
        assert subtract(0.3, 0.1) == pytest.approx(0.2)

    def test_zero(self):
        assert subtract(5, 0) == 5
        assert subtract(0, 5) == -5
        assert subtract(0, 0) == 0

    def test_same_number(self):
        assert subtract(7, 7) == 0


# ─── multiply ─────────────────────────────────────────────────────────────────

class TestMultiply:
    def test_positive_numbers(self):
        assert multiply(3, 4) == 12

    def test_negative_numbers(self):
        assert multiply(-3, -4) == 12

    def test_mixed_sign(self):
        assert multiply(-3, 4) == -12

    def test_floats(self):
        assert multiply(0.5, 0.4) == pytest.approx(0.2)

    def test_zero(self):
        assert multiply(0, 99) == 0
        assert multiply(99, 0) == 0

    def test_one(self):
        assert multiply(1, 42) == 42
        assert multiply(42, 1) == 42


# ─── divide ───────────────────────────────────────────────────────────────────

class TestDivide:
    def test_positive_numbers(self):
        assert divide(10, 2) == 5

    def test_negative_numbers(self):
        assert divide(-10, -2) == 5

    def test_mixed_sign(self):
        assert divide(-10, 2) == -5

    def test_floats(self):
        assert divide(1, 3) == pytest.approx(0.3333333)

    def test_divide_by_one(self):
        assert divide(7, 1) == 7

    def test_zero_numerator(self):
        assert divide(0, 5) == 0

    def test_divide_by_zero_raises(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)

    def test_divide_negative_by_zero_raises(self):
        with pytest.raises(ValueError):
            divide(-5, 0)


# ─── calculate ────────────────────────────────────────────────────────────────

class TestCalculate:
    def test_add_operator(self):
        assert calculate(2, "+", 3) == 5

    def test_subtract_operator(self):
        assert calculate(10, "-", 4) == 6

    def test_multiply_operator(self):
        assert calculate(3, "*", 7) == 21

    def test_divide_operator(self):
        assert calculate(15, "/", 3) == 5

    def test_unknown_operator_raises(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            calculate(1, "^", 2)

    def test_modulo_operator_not_supported(self):
        with pytest.raises(ValueError):
            calculate(10, "%", 3)

    def test_divide_by_zero_via_calculate(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calculate(5, "/", 0)

    def test_float_operands(self):
        assert calculate(0.1, "+", 0.2) == pytest.approx(0.3)

    def test_negative_operands(self):
        assert calculate(-5, "+", -3) == -8
        assert calculate(-5, "-", -3) == -2
        assert calculate(-5, "*", -3) == 15
        assert calculate(-6, "/", -3) == 2
