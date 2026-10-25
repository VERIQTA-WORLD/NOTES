"""Lazy SDK imports keep the unit tests credential- and network-free."""
import time
import random

class DeadlineError(TimeoutError):
    pass

RETRYABLE = {"ThrottlingException", "Throttling", "TooManyRequestsException",
             "RequestLimitExceeded", "SlowDown", "ServiceUnavailableException",
             "InternalServerException", "RequestTimeout", "ModelNotReadyException"}

def error_code(exc):
    return getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)

def ensure_time(deadline, minimum=0.25):
    if deadline-time.monotonic() < minimum:
        raise DeadlineError("Request time budget exhausted; try a smaller question.")

class Factory:
    def __init__(self):
        import boto3
        # Boto3's normal chain: local SSO/profile, or Lambda's execution role.
        self.session = boto3.Session()

    def client(self, service, region, deadline):
        from botocore.config import Config
        ensure_time(deadline, 1)
        remaining = deadline-time.monotonic()
        return self.session.client(service, region_name=region, config=Config(
            connect_timeout=min(1, remaining/4), read_timeout=min(6, remaining/2),
            retries={"mode": "standard", "total_max_attempts": 1}))

    def table(self, name, region):
        from botocore.config import Config
        return self.session.resource("dynamodb", region_name=region, config=Config(
            connect_timeout=1, read_timeout=2,
            retries={"mode": "standard", "total_max_attempts": 1})).Table(name)

def call_read(operation, deadline, **kwargs):
    # Exactly one retry layer; only bounded reads/inference use this wrapper.
    # Inference retries can repeat billed work after an ambiguous network error.
    for attempt in range(2):
        ensure_time(deadline)
        try:
            return operation(**kwargs)
        except Exception as exc:
            retryable = error_code(exc) in RETRYABLE or type(exc).__name__ in {
                "ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError"}
            if not retryable or attempt == 1:
                raise
            delay = random.uniform(0, 0.3 * 2**attempt)
            ensure_time(deadline, delay+1)
            time.sleep(delay)
