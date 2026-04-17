import string

from app.utils.request_codes import generate_request_code


def test_generate_request_code_uses_prefix_and_alphanumeric_suffix():
    code = generate_request_code(prefix="PAY")

    prefix, suffix = code.split("-", 1)
    assert prefix == "PAY"
    assert len(suffix) == 6
    assert set(suffix) <= set(string.ascii_uppercase + string.digits)


def test_generate_request_code_is_not_sequential():
    codes = {generate_request_code(prefix="REQ") for _ in range(50)}
    assert len(codes) == 50
