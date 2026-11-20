import pytest


def test_logic():
    assert 1 + 1 == 2


@pytest.mark.hardware
def test_motor_spins():
    raise RuntimeError("touched hardware!")
