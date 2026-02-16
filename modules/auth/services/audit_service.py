"""Audit logging — append-only security event recording."""

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def log_audit(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    api_key_id: str | None = None,
    action: str,
    resource: str,
    resource_id: str | None = None,
    ip_address: str | None = None,
    payload: Any | None = None,
) -> None:
    """Insert an immutable audit log entry.

    ``payload`` is SHA-256 hashed — raw sensitive data is never stored.
    """
    payload_hash: str | None = None
    if payload is not None:
        raw = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(raw.encode()).hexdigest()

    await db.execute(
        text(
            "INSERT INTO core.audit_log "
            "(user_id, api_key_id, action, resource, resource_id, ip_address, payload_hash) "
            "VALUES (:uid, :kid, :action, :resource, :rid, :ip, :ph)"
        ),
        {
            "uid": user_id,
            "kid": api_key_id,
            "action": action,
            "resource": resource,
            "rid": resource_id,
            "ip": ip_address,
            "ph": payload_hash,
        },
    )
    await db.commit()
