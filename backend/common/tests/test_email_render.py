from typing import Any

import pytest
from django.core import mail

from common.email.render import build_message, render_html


@pytest.fixture(autouse=True)
def frontend_url(settings: Any) -> None:
    settings.FRONTEND_URL = "https://app.example.com"


def html_of(message: mail.EmailMultiAlternatives) -> str:
    return str(message.alternatives[0][0])


class TestEmailRender:
    def test_first_link_becomes_a_button_and_leaves_the_text(self) -> None:
        message = build_message(
            "Verify your email",
            "Confirm your email within 24 hours:\n\n"
            "https://app.example.com/verify-email/abc\n",
            "ada@example.com",
        )
        html = html_of(message)
        assert 'href="https://app.example.com/verify-email/abc"' in html
        assert "Verify email" in html  # label chosen from the link
        assert "Confirm your email within 24 hours." in html
        assert message.body.count("verify-email/abc") == 1

    def test_css_is_inlined(self) -> None:
        html = render_html("Hi", "Hello.\n")
        assert "<style" not in html
        assert 'style="' in html

    def test_no_link_means_no_button(self) -> None:
        assert "Button not working" not in render_html("Removed", "You were removed.\n")

    def test_explicit_label_wins(self) -> None:
        html = render_html("x", "Go https://app.example.com/login\n", "Do it")
        assert "Do it" in html

    def test_text_is_escaped(self) -> None:
        html = render_html("<b>x</b>", "<script>alert(1)</script>\n")
        assert "<script>" not in html
        assert "<b>x</b>" not in html

    def test_sent_through_the_outbox(self) -> None:
        build_message("Hi", "Hello.\n", "ada@example.com").send()
        assert mail.outbox[0].to == ["ada@example.com"]
