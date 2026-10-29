"""Every email Querylab sends through allauth, with sample context, so the
templates can be tested and previewed (`send_test_emails`)."""

from typing import Any

from allauth.account.adapter import get_adapter
from allauth.core.context import request_context
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.test import RequestFactory
from django.utils import timezone

ACCOUNT_EMAILS = (
    "account/email/email_confirmation_signup",
    "account/email/email_confirmation",
    "account/email/password_reset_key",
    "account/email/password_changed",
    "account/email/password_set",
    "account/email/email_changed",
    "account/email/email_confirm",
    "account/email/email_deleted",
    "account/email/account_already_exists",
    "account/email/unknown_account",
    "account/email/login_code",
)


def sample_context(email: str) -> dict[str, Any]:
    frontend = settings.FRONTEND_URL
    return {
        "email": email,
        "activate_url": f"{frontend}/verify-email/sample-key",
        "password_reset_url": f"{frontend}/reset-password/sample-key",
        "signup_url": f"{frontend}/signup",
        "from_email": "old@example.com",
        "to_email": email,
        "deleted_email": "old@example.com",
        "ip": "203.0.113.7",
        "user_agent": "Mozilla/5.0 (sample)",
        "timestamp": timezone.now(),
    }


# Emails that carry a one-time code instead of a link.
CODE_EMAILS = ("account/email/login_code",)
SAMPLE_CODE = "ABC123"


def render_account_email(template_prefix: str, email: str) -> EmailMultiAlternatives:
    context = sample_context(email)
    if template_prefix in CODE_EMAILS:
        context["code"] = SAMPLE_CODE
    request = RequestFactory().get("/")
    with request_context(request):
        message = get_adapter().render_mail(template_prefix, email, context)
    assert isinstance(message, EmailMultiAlternatives)
    return message
