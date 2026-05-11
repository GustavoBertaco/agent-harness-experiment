import os
import sys
import json
import logging
from dataclasses import dataclass
from typing import Tuple, List

logger = logging.getLogger(__name__)

_DEFAULT_PAYLOAD_TEMPLATE = json.dumps({
    "id": "uuid",
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "status": "choice(active,inactive,pending)",
    "amount": "decimal(2)",
    "description": "string(32)",
})

_VALID_OPS = {"c", "u", "d"}


@dataclass(frozen=True)
class OperationWeights:
    c: float
    u: float
    d: float

    @classmethod
    def parse(cls, raw: str) -> "OperationWeights":
        try:
            parts = [p.strip() for p in raw.split(",")]
            parsed = {}
            for part in parts:
                op, val = part.split(":")
                op = op.strip()
                val = float(val.strip())
                if op not in _VALID_OPS:
                    logger.error("Unrecognized OP_WEIGHTS token: %r", op)
                    sys.exit(1)
                parsed[op] = val
            if set(parsed.keys()) != _VALID_OPS:
                logger.error("OP_WEIGHTS must contain exactly c, u, d. Got: %s", list(parsed))
                sys.exit(1)
        except (ValueError, AttributeError) as e:
            logger.error("OP_WEIGHTS malformed: %r — %s", raw, e)
            sys.exit(1)

        total = sum(parsed.values())
        if abs(total - 100.0) > 0.001:
            logger.error("OP_WEIGHTS must sum to 100 (got %.4f)", total)
            sys.exit(1)

        return cls(c=parsed["c"], u=parsed["u"], d=parsed["d"])

    def as_choices(self) -> Tuple[List[str], List[float]]:
        return ["c", "u", "d"], [self.c, self.u, self.d]


@dataclass(frozen=True)
class ProducerConfig:
    bootstrap_servers: str = "localhost:9092"
    topic: str = "cdc-events"
    event_rate: int = 100
    schema_registry_url: str = ""
    payload_template: str = _DEFAULT_PAYLOAD_TEMPLATE
    op_weights: OperationWeights = None

    def __new__(cls, **kwargs):
        return object.__new__(cls)

    def __init__(self, **_kwargs):
        env = os.environ

        bootstrap_servers = env.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        if not bootstrap_servers:
            logger.error("KAFKA_BOOTSTRAP_SERVERS must not be empty")
            sys.exit(1)

        topic = env.get("KAFKA_TOPIC", "cdc-events")
        if not topic:
            logger.error("KAFKA_TOPIC must not be empty")
            sys.exit(1)

        raw_rate = env.get("EVENT_RATE_PER_SEC", "100")
        try:
            event_rate = int(raw_rate)
        except ValueError:
            logger.error("EVENT_RATE_PER_SEC must be an integer, got: %r", raw_rate)
            sys.exit(1)
        if not (1 <= event_rate <= 10000):
            logger.error("EVENT_RATE_PER_SEC must be 1–10000, got: %d", event_rate)
            sys.exit(1)

        schema_registry_url = env.get("SCHEMA_REGISTRY_URL", "")
        payload_template = env.get("PAYLOAD_TEMPLATE", _DEFAULT_PAYLOAD_TEMPLATE)
        op_weights_raw = env.get("OP_WEIGHTS", "c:70,u:20,d:10")
        op_weights = OperationWeights.parse(op_weights_raw)

        object.__setattr__(self, "bootstrap_servers", bootstrap_servers)
        object.__setattr__(self, "topic", topic)
        object.__setattr__(self, "event_rate", event_rate)
        object.__setattr__(self, "schema_registry_url", schema_registry_url)
        object.__setattr__(self, "payload_template", payload_template)
        object.__setattr__(self, "op_weights", op_weights)
