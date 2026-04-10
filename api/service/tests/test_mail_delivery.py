import smtplib
import unittest
from unittest.mock import patch

from service.mail_delivery import send_mail_checked


class MailDeliveryTests(unittest.TestCase):
    @patch("service.mail_delivery.send_mail")
    def test_send_mail_checked_success(self, send_mail_mock):
        send_mail_mock.return_value = 1

        result = send_mail_checked(
            "Asunto",
            "Cuerpo",
            "destino@example.com",
            html_body="<p>Cuerpo</p>",
            from_email="no-reply@example.com",
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["sent"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["delivered"], 1)

    @patch("service.mail_delivery.send_mail")
    def test_send_mail_checked_returns_auth_failure_payload(self, send_mail_mock):
        send_mail_mock.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

        result = send_mail_checked(
            "Asunto",
            "Cuerpo",
            "destino@example.com",
            from_email="no-reply@example.com",
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["sent"])
        self.assertEqual(result["error_code"], "smtp_auth_failed")
        self.assertEqual(result["status"], 502)
        self.assertIn("autenticar", result["detail"].lower())

    @patch("service.mail_delivery.send_mail")
    def test_send_mail_checked_returns_unconfirmed_when_provider_returns_zero(self, send_mail_mock):
        send_mail_mock.return_value = 0

        result = send_mail_checked(
            "Asunto",
            "Cuerpo",
            "destino@example.com",
            from_email="no-reply@example.com",
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["sent"])
        self.assertEqual(result["error_code"], "smtp_not_confirmed")
        self.assertEqual(result["status"], 502)

    def test_send_mail_checked_rejects_missing_recipient(self):
        result = send_mail_checked(
            "Asunto",
            "Cuerpo",
            "",
            from_email="no-reply@example.com",
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["sent"])
        self.assertEqual(result["error_code"], "smtp_recipient_missing")
        self.assertEqual(result["status"], 400)


if __name__ == "__main__":
    unittest.main()
