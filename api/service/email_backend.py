import ssl

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend
from django.utils.functional import cached_property


class EmailBackend(DjangoSMTPEmailBackend):
    """
    SMTP backend with optional TLS certificate verification bypass.

    Intended as a temporary workaround for SMTP servers with expired/misconfigured
    certificates. Enable only with EMAIL_INSECURE_SKIP_VERIFY=1.
    """

    @cached_property
    def ssl_context(self):
        if getattr(settings, "EMAIL_INSECURE_SKIP_VERIFY", False):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            if self.ssl_certfile or self.ssl_keyfile:
                try:
                    ctx.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
                except Exception:
                    pass
            return ctx
        return super().ssl_context
