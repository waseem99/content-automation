from __future__ import annotations

from src.application.workers.models import WorkerFailureClass, WorkerRetryPolicy


class RetryLimitExceeded(RuntimeError):
    pass


def is_retryable(failure_class: WorkerFailureClass, policy: WorkerRetryPolicy) -> bool:
    return failure_class in policy.retryable_failures


def can_retry(*, failure_class: WorkerFailureClass, completed_attempts: int, policy: WorkerRetryPolicy) -> bool:
    return is_retryable(failure_class, policy) and completed_attempts < policy.max_attempts


def next_attempt_number(*, completed_attempts: int, policy: WorkerRetryPolicy, failure_class: WorkerFailureClass) -> int:
    if not can_retry(failure_class=failure_class, completed_attempts=completed_attempts, policy=policy):
        raise RetryLimitExceeded("Worker retry limit exceeded")
    return completed_attempts + 1
