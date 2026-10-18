"""Signing the Floor Manifest (PRD F5.4, AC-F5): the inputs of `cosign attest` and a check of its output.

cosign signs in CI, keyless: it trades the job's GitLab ID token for a short-lived Sigstore certificate.
The identity in that certificate is the pipeline definition at one ref, from the `ci_config_ref_uri`
claim. This module never signs and never sets a floor. It only
- splits the manifest (an in-toto Statement) into its predicate and predicate type, which cosign wraps again;
- reads the identity from the ID token, so that the verify step checks that exact identity;
- checks that an attestation that cosign verified has the predicate of the manifest on the same digest.
"""

from __future__ import annotations

import base64
import json

from . import manifest

PAYLOAD_TYPE = "application/vnd.in-toto+json"


def predicate(statement: dict) -> tuple[str, dict]:
    """The predicate type and the predicate of a floor manifest."""
    if statement.get("_type") != manifest.STATEMENT_TYPE or "predicate" not in statement:
        raise ValueError("not a floor manifest: no in-toto Statement with a predicate")
    return statement["predicateType"], statement["predicate"]


def identity(token: str) -> str:
    """The certificate identity that Sigstore gives a GitLab CI job: https:// and the ci_config_ref_uri claim.

    The token is not verified here (Sigstore does that). Only this one claim is read, because the token
    also has claims about the person who started the pipeline.
    """
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("the ID token is not a JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    uri = json.loads(base64.urlsafe_b64decode(payload)).get("ci_config_ref_uri")
    if not uri:
        raise ValueError("the ID token has no ci_config_ref_uri claim")
    return "https://" + uri


def statements(verified: str) -> list[dict]:
    """The in-toto Statements in the output of `cosign verify-attestation` (one DSSE envelope per line)."""
    found = []
    for line in verified.splitlines():
        if not line.strip():
            continue
        envelope = json.loads(line)
        if envelope.get("payloadType") == PAYLOAD_TYPE:
            found.append(json.loads(base64.b64decode(envelope["payload"])))
    return found


def check(statement: dict, verified: str) -> str | None:
    """None when a verified attestation has the predicate of the manifest on its digest, else the reason."""
    kind, pred = predicate(statement)
    digest = statement["subject"][0]["digest"]["sha256"]
    found = statements(verified)
    if not found:
        return "cosign verified no in-toto attestation"
    same = [s for s in found if s.get("predicateType") == kind
            and any(sub.get("digest", {}).get("sha256") == digest for sub in s.get("subject", []))]
    if not same:
        return f"no verified attestation of type {kind} on sha256:{digest}"
    if not any(s.get("predicate") == pred for s in same):
        return "the verified attestation has a different predicate from the manifest"
    return None
