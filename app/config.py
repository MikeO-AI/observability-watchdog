"""Runtime configuration, sourced from environment variables with safe defaults.

Kept dependency-free (plain os.getenv) so the service boots with zero setup.
"""
import os

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./watchdog.db")
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

        # Detection tuning
        self.bucket_seconds = int(os.getenv("BUCKET_SECONDS", "60"))
        self.baseline_window = int(os.getenv("BASELINE_WINDOW", "3"))
        self.zscore_threshold = float(os.getenv("ZSCORE_THRESHOLD", "3.0"))
        self.min_error_count = int(os.getenv("MIN_ERROR_COUNT", "3"))

        # Alerting
        self.alert_severity = os.getenv("ALERT_SEVERITY", "high").lower()
        self.webhook_url = os.getenv("WEBHOOK_URL", "").strip()

    def should_alert(self, severity: str) -> bool:
        """True when an anomaly's severity meets or exceeds the alert threshold."""
        return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(self.alert_severity, 2)


settings = Settings()
