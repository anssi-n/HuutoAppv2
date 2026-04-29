from functools import wraps
from typing import Any
from collections.abc import Callable
from time import sleep
from logger import logger

class RetryLimitExceeded(Exception):
    pass

def retry[R, **P](*, retries: int, delay: int) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def retry_decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def retry_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            new_kwargs: dict[str,Any] = {}
            for i in range(retries+1):
                try:
                    return func(*args, **(kwargs | new_kwargs)) # type: ignore
                except BaseException as err:
                    logger.info(f"Exception {err.__class__.__qualname__}:{err} occured while executing {func.__name__}. {i+1}/{retries+1}.")
                    if hasattr(err, "new_kwargs") and isinstance(err.new_kwargs,dict):
                        logger.info(f"New keyword arguments {err.new_kwargs} defined in exception. Adding new arguments to next function call.")
                        new_kwargs = err.new_kwargs
                    sleep(delay)

            raise RetryLimitExceeded(
                f"{func.__name__}, {retries=}, {delay=}")

        return retry_wrapper
    return retry_decorator