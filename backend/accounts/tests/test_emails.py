import pytest
from django.core import mail
from django.core.management import call_command

from accounts.emails import ACCOUNT_EMAILS, render_account_email


@pytest.mark.parametrize("template_prefix", ACCOUNT_EMAILS)
def test_every_email_has_text_and_inlined_html(template_prefix: str) -> None:
    message = render_account_email(template_prefix, "ada@example.com")
    assert message.body.strip()
    assert "{%" not in message.body and "{{" not in message.body
    html = str(message.alternatives[0][0])
    assert message.alternatives[0][1] == "text/html"
    assert "<style" not in html
    assert "Querylab" in html
    assert message.subject and "\n" not in message.subject


def test_links_become_buttons() -> None:
    message = render_account_email(
        "account/email/email_confirmation_signup", "ada@example.com"
    )
    html = str(message.alternatives[0][0])
    assert "/verify-email/sample-key" in html
    assert "Verify email" in html


def test_send_test_emails_sends_each_once() -> None:
    call_command("send_test_emails", "ada@example.com")
    assert len(mail.outbox) == len(ACCOUNT_EMAILS)
    assert {message.to[0] for message in mail.outbox} == {"ada@example.com"}
