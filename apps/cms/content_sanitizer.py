from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit


_ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "em",
    "h2",
    "h3",
    "h4",
    "li",
    "ol",
    "p",
    "s",
    "span",
    "strong",
    "u",
    "ul",
}
_VOID_TAGS = {"br"}
_BLOCKED_TAGS = {"iframe", "object", "script", "style", "svg", "template"}
_TEXT_SIZES = {"small", "normal", "large", "xlarge"}
_ALIASES = {"b": "strong", "i": "em"}


class _AboutHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.plain_text = []
        self.open_tags = []
        self.blocked_tags = []
        self.has_formatting = False

    def handle_starttag(self, tag, attrs):
        if self.blocked_tags:
            if tag not in _VOID_TAGS:
                self.blocked_tags.append(tag)
            return
        if tag in _BLOCKED_TAGS:
            self.blocked_tags.append(tag)
            return
        self._open_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        if self.blocked_tags or tag in _BLOCKED_TAGS:
            return
        self._open_tag(tag, attrs)
        if tag not in _VOID_TAGS and tag in _ALLOWED_TAGS:
            self._close_tag(tag)

    def handle_endtag(self, tag):
        if self.blocked_tags:
            if tag in self.blocked_tags:
                del self.blocked_tags[len(self.blocked_tags) - 1 - self.blocked_tags[::-1].index(tag):]
            return
        self._close_tag(tag)

    def handle_data(self, data):
        if self.blocked_tags:
            return
        self.plain_text.append(data)
        self.parts.append(escape(data))

    def finish(self):
        self.close()
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        if not self.has_formatting:
            return _plain_text_to_html("".join(self.plain_text))
        return "".join(self.parts).strip()

    def _open_tag(self, tag, attrs):
        tag = _ALIASES.get(tag, tag)
        if tag not in _ALLOWED_TAGS:
            return
        if tag in {"p", "h2", "h3", "h4", "blockquote", "ul", "ol"} and self.open_tags:
            if self.open_tags[-1] == "p":
                self._close_tag("p")

        attributes = dict(attrs)
        serialized_attrs = ""
        if tag == "a":
            href = attributes.get("href", "").strip()
            if self._is_safe_link(href):
                serialized_attrs = f' href="{escape(href, quote=True)}"'
        elif tag == "span" and attributes.get("data-text-size") in _TEXT_SIZES:
            serialized_attrs = f' data-text-size="{attributes["data-text-size"]}"'

        self.parts.append(f"<{tag}{serialized_attrs}>")
        self.has_formatting = True
        if tag not in _VOID_TAGS:
            self.open_tags.append(tag)

    def _close_tag(self, tag):
        tag = _ALIASES.get(tag, tag)
        if tag not in self.open_tags:
            return
        position = len(self.open_tags) - 1 - self.open_tags[::-1].index(tag)
        while len(self.open_tags) > position:
            self.parts.append(f"</{self.open_tags.pop()}>")

    @staticmethod
    def _is_safe_link(href):
        if not href or "\\" in href or any(ord(character) < 32 for character in href):
            return False
        if href.startswith("/") and not href.startswith("//"):
            return True
        parsed = urlsplit(href)
        if parsed.scheme in {"http", "https"}:
            return bool(parsed.netloc)
        return parsed.scheme == "mailto" and bool(parsed.path) and not parsed.netloc


def sanitize_about_content(value):
    parser = _AboutHTMLSanitizer()
    parser.feed(value or "")
    return parser.finish()


def _plain_text_to_html(value):
    blocks = []
    paragraph = []

    def flush_paragraph():
        if paragraph:
            blocks.append(f"<p>{'<br>'.join(escape(line) for line in paragraph)}</p>")
            paragraph.clear()

    for line in value.splitlines():
        text = line.strip()
        if not text:
            flush_paragraph()
        elif _is_standalone_heading(text):
            flush_paragraph()
            blocks.append(f"<h2>{escape(text)}</h2>")
        else:
            paragraph.append(text)
    flush_paragraph()
    return "".join(blocks)


def _is_standalone_heading(text):
    return (
        len(text) <= 90
        and not text.endswith((".", "!", ":", ";", ","))
        and (text.endswith("?") or text[0].isupper())
    )
