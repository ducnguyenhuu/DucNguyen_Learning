"""
calculator.py — Simple calculation module with basic arithmetic operators.
"""


def add(a: float, b: float) -> float:
    """Return the sum of a and b."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference of a and b (a - b)."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of a and b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return the quotient of a and b (a / b).

    Raises:
        ValueError: If b is zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def calculate(a: float, operator: str, b: float) -> float:
    """Evaluate a simple arithmetic expression.

    Args:
        a: Left operand.
        operator: One of '+', '-', '*', '/'.
        b: Right operand.

    Returns:
        Result of the operation.

    Raises:
        ValueError: For unknown operators or division by zero.
    """
    ops = {
        "+": add,
        "-": subtract,
        "*": multiply,
        "/": divide,
    }
    if operator not in ops:
        raise ValueError(f"Unknown operator: '{operator}'. Use one of: {list(ops)}")
    return ops[operator](a, b)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python calculator.py <num> <op> <num>")
        print("Example: python calculator.py 10 + 5")
        sys.exit(1)

    try:
        result = calculate(float(sys.argv[1]), sys.argv[2], float(sys.argv[3]))
        print(f"{sys.argv[1]} {sys.argv[2]} {sys.argv[3]} = {result}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
