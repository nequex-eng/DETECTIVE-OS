import unittest

from deploy import resolve_cloudflare_token


class TestDeployCredentialResolution(unittest.TestCase):
    def test_standard_environment_token_takes_precedence(self):
        token = resolve_cloudflare_token(
            {"CLOUDFLARE_API_TOKEN": "test-token"},
            credential_loader=lambda *_: {"surrogate": "hsurr:ignored"})
        self.assertEqual(token, "test-token")

    def test_muse_fallback_is_used_only_when_standard_token_missing(self):
        token = resolve_cloudflare_token(
            {},
            credential_loader=lambda *_: {"surrogate": "hsurr:temporary"})
        self.assertEqual(token, "hsurr:temporary")

    def test_invalid_or_missing_credentials_fail_closed(self):
        self.assertEqual(resolve_cloudflare_token({}, credential_loader=lambda *_: {}), "")
        self.assertEqual(resolve_cloudflare_token({}, credential_loader=lambda *_: {"surrogate": "bad"}), "")


if __name__ == "__main__":
    unittest.main()
