import re
from detect_secrets.plugins.base import RegexBasedDetector

# checks if a string contains 'GEMFURY_URL' followed by 'https'
# allowing quotes, apostrophes or spaces in between


class GemfuryDetector(RegexBasedDetector):
    """Scans for Gemfury URL in files not ignored."""

    secret_type = "Gemfury URL"  # pragma: allowlist secret # nosec

    denylist = [re.compile(r'GEMFURY_URL\s*=\s*[\'"\s]*https')]
