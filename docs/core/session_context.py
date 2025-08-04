from dataclasses import dataclass
from config import AppConfig

@dataclass
class SessionContext:
    config: AppConfig
    session_id: str = None
