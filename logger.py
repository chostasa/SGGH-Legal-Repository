import logging
import json
import os
import time
from datetime import datetime

def get_logger(name: str = "legal_automation") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            json.dumps({
                "time": "%(asctime)s",
                "level": "%(levelname)s",
                "message": "%(message)s",
                "module": "%(module)s",
                "funcName": "%(funcName)s",
                "lineno": "%(lineno)d"
            }),
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    return logger

def log_metric(metric_name: str, value: int = 1, metadata: dict = None):
    try:
        logger.info(json.dumps({
            "metric": metric_name,
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }))
    except Exception:
        pass

def log_error_with_metrics(error: Exception, code: str, context: dict = None):
    try:
        logger.error(json.dumps({
            "error_code": code,
            "error": str(error),
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }))
    except Exception:
        pass

logger = get_logger()