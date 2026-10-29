import json
import logging

from common.logger.constants import COLORS, RESET_COLOR


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:

        color = COLORS.get(record.levelno, RESET_COLOR)

        base = super().format(record)

        request_data = getattr(record, "request_data", None)

        if request_data:
            base += "\n" + json.dumps(request_data, indent=2)

        return f"{color}{base}{RESET_COLOR}"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:

        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
        }

        request_data = getattr(record, "request_data", None)
        if request_data:
            payload["request"] = request_data

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
