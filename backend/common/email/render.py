"""Turns a plain-text transactional email into a multipart message: the text
stays as the fallback, and an HTML version adds the Querylab header, a button
for the main link, and a footer. Callers keep passing plain text.

The layout keeps its CSS in one <style> block for readability; css-inline
moves it onto the elements at render time, because Gmail and Outlook drop
<style> blocks."""

import re

import css_inline
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

DEFAULT_ACTION_LABEL = "Open Querylab"

_URL = re.compile(r"https?://[^\s<>\"']+")
# A phrase that introduces a link ("... at <url>", "... : <url>") goes with it.
_LEAD_IN = re.compile(r"\s*(?:\bat|\bto|:)?\s*$")

# Button text by what the link points at, so callers need not name one.
_ACTION_LABELS = (
    ("/verify-email", "Verify email"),
    ("/reset-password", "Reset password"),
    ("/forgot-password", "Reset password"),
    ("/login", "Sign in"),
    ("/signup", "Create account"),
)

_INLINER = css_inline.CSSInliner(keep_style_tags=False, load_remote_stylesheets=False)


def action_label_for(url: str) -> str:
    for fragment, label in _ACTION_LABELS:
        if fragment in url:
            return label
    return DEFAULT_ACTION_LABEL


def _split(body: str) -> tuple[list[str], str | None]:
    """Paragraphs of the body without the first link, and that link. Further
    links stay in the text so nothing is lost."""
    match = _URL.search(body)
    url = match.group(0).rstrip(".,);") if match else None
    if match and url:
        end = match.start() + len(url)
        before = _LEAD_IN.sub("", body[: match.start()])
        body = (
            before
            + ("." if before and not before.endswith((".", "!", "?")) else "")
            + body[end:].lstrip(".")
        )
    paragraphs = [" ".join(chunk.split()) for chunk in re.split(r"\n\s*\n|\n", body)]
    return [p for p in paragraphs if p], url


def render_html(subject: str, body: str, action_label: str | None = None) -> str:
    paragraphs, url = _split(body)
    html = render_to_string(
        "email/base.html",
        {
            "subject": subject,
            "preheader": paragraphs[0] if paragraphs else subject,
            "paragraphs": paragraphs,
            "action_url": url,
            "action_label": action_label or (action_label_for(url) if url else ""),
            "home_url": settings.FRONTEND_URL,
        },
    )
    return _INLINER.inline(html)


def build_message(
    subject: str, body: str, to: str, action_label: str | None = None
) -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
    message.attach_alternative(render_html(subject, body, action_label), "text/html")
    return message
