"""Pretty-print minified HTML with proper indentation.

Uses a script/style-aware tokenizer instead of regex so that JavaScript
containing ``<`` / ``>`` characters inside ``<script>`` blocks does not
break the output.  Produces browser-DevTools-style indentation (2 spaces).
"""

from __future__ import annotations

import re

VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

# Elements whose content is raw text (not parsed as HTML).
RAW_TEXT_ELEMENTS = frozenset({"script", "style"})

_CLOSE_TAG_RE = re.compile(r"</([a-zA-Z][a-zA-Z0-9]*)\s*>")
_OPEN_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)")


def _tokenize(raw: str) -> list[tuple]:
    """Split HTML into a token stream.

    Token types:
    - ("doctype", text)
    - ("comment", text)
    - ("open", tag_name, full_tag_text, is_self_closing)
    - ("close", tag_name, full_tag_text)
    - ("text", text)
    - ("raw", text)  — raw content inside <script> / <style>
    """
    tokens: list[tuple] = []
    pos = 0
    length = len(raw)

    while pos < length:
        if raw[pos] != "<":
            # Text content until next tag
            end = raw.find("<", pos)
            if end == -1:
                end = length
            text = raw[pos:end].strip()
            if text:
                tokens.append(("text", text))
            pos = end
            continue

        # --- We're at a '<' character ---

        # HTML comment
        if raw[pos : pos + 4] == "<!--":
            end = raw.find("-->", pos + 4)
            if end == -1:
                end = length
            else:
                end += 3
            tokens.append(("comment", raw[pos:end]))
            pos = end
            continue

        # DOCTYPE
        if raw[pos : pos + 9].lower() == "<!doctype":
            end = raw.find(">", pos)
            if end == -1:
                end = length
            else:
                end += 1
            tokens.append(("doctype", raw[pos:end]))
            pos = end
            continue

        # Closing tag
        m = _CLOSE_TAG_RE.match(raw, pos)
        if m:
            tokens.append(("close", m.group(1).lower(), m.group(0)))
            pos = m.end()
            continue

        # Opening tag
        m = _OPEN_TAG_RE.match(raw, pos)
        if m:
            tag_name = m.group(1).lower()
            # Walk forward to find the end of the tag, respecting quoted attrs.
            p = m.end()
            while p < length:
                ch = raw[p]
                if ch == ">":
                    p += 1
                    break
                if ch in ('"', "'"):
                    # Skip quoted attribute value
                    q = raw.find(ch, p + 1)
                    p = (q + 1) if q != -1 else length
                else:
                    p += 1

            tag_text = raw[pos:p]
            is_self_closing = tag_text.rstrip().endswith("/>")

            tokens.append(("open", tag_name, tag_text, is_self_closing))

            # Raw-text elements: grab everything up to the matching close tag.
            if tag_name in RAW_TEXT_ELEMENTS:
                close_tag = f"</{tag_name}>"
                close_idx = raw.lower().find(close_tag, p)
                if close_idx == -1:
                    # Unclosed tag — consume the rest
                    remaining = raw[p:]
                    if remaining.strip():
                        tokens.append(("raw", remaining))
                    pos = length
                else:
                    content = raw[p:close_idx]
                    if content.strip():
                        tokens.append(("raw", content))
                    actual_close = raw[close_idx : close_idx + len(close_tag)]
                    tokens.append(("close", tag_name, actual_close))
                    pos = close_idx + len(close_tag)
            else:
                pos = p
            continue

        # Stray '<' that doesn't start a valid construct — emit as text.
        tokens.append(("text", "<"))
        pos += 1

    return tokens


def prettify_html(raw: str) -> str:
    """Pretty-print minified HTML into readable, indented lines.

    Produces output similar to browser DevTools (Elements panel) with 2-space
    indentation.  Correctly handles ``<script>`` / ``<style>`` blocks that
    contain ``<`` and ``>`` in their JavaScript or CSS content.
    """
    tokens = _tokenize(raw)
    result: list[str] = []
    indent = 0
    pad = "  "

    for token in tokens:
        kind = token[0]

        if kind == "doctype":
            result.append(pad * indent + token[1])

        elif kind == "comment":
            result.append(pad * indent + token[1])

        elif kind == "text":
            result.append(pad * indent + token[1])

        elif kind == "raw":
            # Script/style content — indent each non-empty line.
            for line in token[1].split("\n"):
                stripped = line.strip()
                if stripped:
                    result.append(pad * indent + stripped)

        elif kind == "close":
            indent = max(0, indent - 1)
            result.append(pad * indent + token[2])

        elif kind == "open":
            tag_name = token[1]
            tag_text = token[2]
            is_self_closing = token[3]
            is_void = tag_name in VOID_ELEMENTS

            result.append(pad * indent + tag_text)

            if not is_self_closing and not is_void:
                indent += 1

    return "\n".join(result)
