"""Smoke-тест утилит форматирования текста."""

from services.text_formatter import (
    apply_bold,
    apply_italic,
    apply_link,
    apply_strike,
    apply_underline,
)


def test_apply_bold():
    assert apply_bold("hello world", "world") == "hello <b>world</b>"


def test_apply_italic():
    assert apply_italic("hello world", "hello") == "<i>hello</i> world"


def test_apply_underline():
    assert apply_underline("ab cd", "ab") == "<u>ab</u> cd"


def test_apply_strike():
    assert apply_strike("ab cd", "cd") == "ab <s>cd</s>"


def test_apply_link():
    assert (
        apply_link("click here", "here", "https://example.com")
        == 'click <a href="https://example.com">here</a>'
    )


def test_fragment_not_found_unchanged():
    assert apply_bold("hello", "xyz") == "hello"
