"""
backend/app/models/recommendation_store.py
───────────────────────────────────────────
Phase 2: In-memory store for pending ApprovalRequest objects.

Keyed by recommendation_id (UUID string).
The store is a process-level singleton — a full restart clears all pending
recommendations.  This is intentional: pending recommendations are
time-sensitive and should not survive server restarts.

Approved/rejected decisions are persisted to OperatorLog in SQLite by the
approve endpoint in main.py — that is the durable record of human decisions.
This store is only for the ephemeral pending-approval lifecycle.

Thread safety: a threading.Lock protects all mutations.  FastAPI's async
endpoints call store methods via run_in_executor if needed; for this
prototype the store is small enough that sync access is acceptable.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional

from app.sim.signal_plan import ApprovalRequest


class RecommendationStore:
    """
    Singleton in-memory store.  Use the module-level `store` instance.

    Lifecycle states for a recommendation:
        PENDING    → awaiting operator decision
        APPROVED   → operator approved, apply endpoint has been called
        REJECTED   → operator explicitly rejected
        APPLIED    → TraCI plan was successfully deployed to SUMO
        ROLLED_BACK→ plan was applied then reverted
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, ApprovalRequest] = {}

    # ── Write operations ──────────────────────────────────────────────────

    def add(self, request: ApprovalRequest) -> None:
        """Store a new ApprovalRequest.  Raises if the ID already exists."""
        with self._lock:
            if request.recommendation_id in self._records:
                raise KeyError(
                    f"Recommendation {request.recommendation_id} already exists. "
                    "Each recommendation must have a unique ID."
                )
            self._records[request.recommendation_id] = request

    def update_status(self, recommendation_id: str, new_status: str) -> ApprovalRequest:
        """
        Transition a recommendation to a new status.
        Raises KeyError if not found; raises ValueError for invalid transitions.
        """
        valid_statuses = {"PENDING", "APPROVED", "REJECTED", "APPLIED", "ROLLED_BACK"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status {new_status!r}. Valid: {valid_statuses}")

        with self._lock:
            if recommendation_id not in self._records:
                raise KeyError(f"Recommendation {recommendation_id!r} not found.")
            rec = self._records[recommendation_id]
            # Enforce valid transitions
            current = rec.status
            allowed_from: Dict[str, set] = {
                "PENDING":     {"APPROVED", "REJECTED"},
                "APPROVED":    {"APPLIED"},
                "APPLIED":     {"ROLLED_BACK"},
                "REJECTED":    set(),      # terminal
                "ROLLED_BACK": set(),      # terminal
            }
            if new_status not in allowed_from.get(current, set()):
                raise ValueError(
                    f"Cannot transition recommendation {recommendation_id!r} "
                    f"from {current!r} to {new_status!r}. "
                    f"Allowed from {current!r}: {allowed_from.get(current, set())}"
                )
            # Pydantic models are not mutable by default — recreate with updated status
            updated = rec.model_copy(update={"status": new_status})
            self._records[recommendation_id] = updated
            return updated

    # ── Read operations ───────────────────────────────────────────────────

    def get(self, recommendation_id: str) -> Optional[ApprovalRequest]:
        """Return the ApprovalRequest or None if not found."""
        with self._lock:
            return self._records.get(recommendation_id)

    def get_or_raise(self, recommendation_id: str) -> ApprovalRequest:
        """Return the ApprovalRequest or raise KeyError."""
        rec = self.get(recommendation_id)
        if rec is None:
            raise KeyError(f"Recommendation {recommendation_id!r} not found.")
        return rec

    def list_pending(self) -> list[ApprovalRequest]:
        """Return all recommendations in PENDING state."""
        with self._lock:
            return [r for r in self._records.values() if r.status == "PENDING"]

    def list_all(self) -> list[ApprovalRequest]:
        """Return all recommendations in any state."""
        with self._lock:
            return list(self._records.values())

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def has_active_intervention(self, tls_id: str) -> bool:
        """
        Return True if any recommendation currently in APPLIED status covers tls_id.

        Used by the approve endpoint to prevent overlapping concurrent deployments:
        a second recommendation for a TLS that already has an APPLIED plan cannot
        be approved until the first is rolled back or otherwise resolved.
        """
        with self._lock:
            for rec in self._records.values():
                if rec.status != "APPLIED":
                    continue
                for c in rec.proposal.candidates:
                    if c.tls_id == tls_id and "HOLD" not in c.rationale:
                        return True
        return False



# Module-level singleton — import this in main.py and manager.py
store = RecommendationStore()
