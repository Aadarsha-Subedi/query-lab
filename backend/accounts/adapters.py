from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django import forms
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives

from common.email.render import render_html
from common.validators.constants import DISPOSABLE_EMAIL_MESSAGE
from common.validators.disposable import is_disposable


class AccountAdapter(DefaultAccountAdapter):
    def render_mail(
        self,
        template_prefix: str,
        email: str | list[str],
        context: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> EmailMessage:
        """allauth renders the plain-text email from our templates; every one
        then gets the styled HTML version of the same text."""
        message = super().render_mail(template_prefix, email, context, headers)
        if isinstance(message, EmailMultiAlternatives) and not message.alternatives:
            message.attach_alternative(
                render_html(str(message.subject), str(message.body)), "text/html"
            )
        return message

    def clean_email(self, email: str) -> str:
        if settings.BLOCK_DISPOSABLE_EMAILS and is_disposable(email):
            raise forms.ValidationError(DISPOSABLE_EMAIL_MESSAGE)
        return super().clean_email(email)
