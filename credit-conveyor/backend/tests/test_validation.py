from app.services.pipeline import inn_is_valid


def test_valid_inn_10_and_12_digits():
    assert inn_is_valid("7701234567")
    assert inn_is_valid("770100001700")


def test_empty_inn_rejected():
    assert not inn_is_valid("")
    assert not inn_is_valid("   ")


def test_zero_inn_rejected():
    assert not inn_is_valid("0")
    assert not inn_is_valid("0000000000")


def test_non_digit_and_wrong_length_rejected():
    assert not inn_is_valid("abc")
    assert not inn_is_valid("123")
    assert not inn_is_valid("77012345")
