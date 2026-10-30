import signal

from contextlib import contextmanager
from threading import current_thread, main_thread


class BehaviorTimeout(BaseException):
    """
    Raised when a behavior exceeds its execution time limit.
    """


def handle_behavior_timeout(signum, frame):
    """Handle SIGALRM by interrupting behavior execution."""
    raise BehaviorTimeout()


@contextmanager
def behavior_time_limit(timeout_ms: int):
    """
    Limit behavior execution time using SIGALRM.

    Must be executed in the main thread of a Linux worker process.
    """

    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")

    if current_thread() is not main_thread():
        raise RuntimeError(
            "Behavior timeout must run in the main thread"
        )

    # Avoid interfering with an existing timer.
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError(
            "An ITIMER_REAL timer is already active"
        )

    previous_handler = signal.getsignal(signal.SIGALRM)

    signal.signal(signal.SIGALRM, handle_behavior_timeout)

    try:
        signal.setitimer(
            signal.ITIMER_REAL,
            timeout_ms / 1000,
        )

        yield

    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
