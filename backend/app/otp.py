"""OTP delivery interface. Swap DevOtpProvider for an SMS provider (MSG91/Twilio) later:
implement `OtpProvider.send` and register it in `get_provider`."""
import logging
import secrets
from abc import ABC, abstractmethod

from .config import get_settings

log = logging.getLogger("edunest.otp")


class OtpProvider(ABC):
    @abstractmethod
    def generate(self) -> str: ...

    @abstractmethod
    def send(self, mobile: str, code: str) -> None: ...


class DevOtpProvider(OtpProvider):
    """Fixed code, printed to the console. NEVER use in production."""

    def generate(self) -> str:
        return get_settings().dev_otp_code

    def send(self, mobile: str, code: str) -> None:
        msg = f"[DEV OTP] mobile={mobile} code={code}"
        log.warning(msg)
        print(msg, flush=True)


class SmsOtpProvider(OtpProvider):  # pragma: no cover - slot for a real gateway
    def generate(self) -> str:
        return f"{secrets.randbelow(10**6):06d}"

    def send(self, mobile: str, code: str) -> None:
        raise NotImplementedError("Wire your SMS gateway (MSG91/Twilio) here")


def get_provider() -> OtpProvider:
    return SmsOtpProvider() if get_settings().otp_provider == "sms" else DevOtpProvider()
