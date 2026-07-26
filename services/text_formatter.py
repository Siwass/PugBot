import re


def apply_format(
    text: str,
    fragment: str,
    tag: str,
):
    if fragment not in text:
        return text

    pattern = re.escape(fragment)

    return re.sub(
        pattern,
        lambda m: f"<{tag}>{m.group(0)}</{tag}>",
        text,
        count=1,
    )


def apply_bold(text, fragment):
    return apply_format(
        text,
        fragment,
        "b",
    )


def apply_italic(text, fragment):
    return apply_format(
        text,
        fragment,
        "i",
    )


def apply_underline(text, fragment):
    return apply_format(
        text,
        fragment,
        "u",
    )


def apply_strike(text, fragment):
    return apply_format(
        text,
        fragment,
        "s",
    )


def apply_link(
    text: str,
    fragment: str,
    url: str,
):
    if fragment not in text:
        return text

    return text.replace(
        fragment,
        f'<a href="{url}">{fragment}</a>',
        1,
    )