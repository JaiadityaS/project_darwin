"""Floor policy: load, validate against the JSON Schema, and resolve per artifact (F1.1)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = PACKAGE_ROOT / "policy.yml"
DEFAULT_SCHEMA = PACKAGE_ROOT / "policy.schema.json"


class PolicyError(ValueError):
    pass


def load(path: str | Path = DEFAULT_POLICY, schema: str | Path = DEFAULT_SCHEMA) -> dict:
    """Reads and validates a policy file. Raises PolicyError with every problem found."""
    try:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyError(f"{path}: not valid YAML: {exc}") from exc
    validate(doc, schema)
    return doc


def validate(doc, schema: str | Path = DEFAULT_SCHEMA) -> None:
    validator = jsonschema.Draft202012Validator(json.loads(Path(schema).read_text(encoding="utf-8")))
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        raise PolicyError("; ".join(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
                                    for e in errors))


def for_artifact(policy: dict, artifact: str | None) -> dict:
    """Returns the policy for one published artifact: its entry replaces the top-level values."""
    resolved = copy.deepcopy({key: value for key, value in policy.items() if key != "artifacts"})
    override = (policy.get("artifacts") or {}).get(artifact or "", {})
    for dimension, values in override.items():
        resolved[dimension] = {**resolved.get(dimension, {}), **values}
    return resolved
