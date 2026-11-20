"""Module docstring: not a comment, allowed."""


def run() -> str:
    """Docstring with a # hash inside."""
    # retry because the serial port sometimes drops the first byte
    marker = "#not-a-comment"
    value = eval("1 + 1")  # noqa: S307 constant expression, no user input
    return f"{marker}{value}"  # REF(pyserial #123): first read after open may be empty
