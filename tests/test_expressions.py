"""Smoke tests that don't require bicep/terraform on PATH."""

from __future__ import annotations

from bicep2tf.expressions import is_arm_expression, translate


def test_arm_expression_detection():
    assert is_arm_expression("[parameters('foo')]")
    assert not is_arm_expression("plain string")
    assert not is_arm_expression("[[escaped]")


def test_translate_literals():
    assert translate(None) == "null"
    assert translate(True) == "true"
    assert translate(42) == "42"
    assert translate("hello") == '"hello"'
    assert translate(["a", "b"]) == '["a", "b"]'


def test_translate_parameters():
    assert translate("[parameters('myParam')]") == "var.my_param"


def test_translate_variables():
    assert translate("[variables('myVar')]") == "local.my_var"


def test_translate_format():
    out = translate("[format('{0}/{1}', parameters('a'), parameters('b'))]")
    assert out == '"${var.a}/${var.b}"'


def test_translate_concat_and_if():
    out = translate("[if(empty(parameters('x')), 'a', 'b')]")
    assert out == '((length(var.x) == 0) ? "a" : "b")'


def test_translate_unsupported_emits_todo():
    out = translate("[someUnknownFunc('x')]")
    assert "TODO" in out
