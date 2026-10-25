import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    region: str
    model_id: str
    allowed_regions: tuple
    data_bucket: str = ""
    log_group: str = ""
    table_name: str = ""

    @classmethod
    def from_env(cls):
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        allowed = tuple(x.strip() for x in os.getenv("ALLOWED_REGIONS", region).split(",") if x.strip())
        model = os.getenv("MODEL_ID", "").strip()
        if not model:
            raise ValueError("Set MODEL_ID to a Converse/tool-use model or inference profile you can invoke.")
        if region not in allowed:
            raise ValueError("AWS_REGION must be in ALLOWED_REGIONS")
        return cls(region, model, allowed, os.getenv("DATA_BUCKET", ""),
                   os.getenv("LOG_GROUP_NAME", ""), os.getenv("TABLE_NAME", ""))
