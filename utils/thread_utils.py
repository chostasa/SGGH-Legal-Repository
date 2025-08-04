import asyncio
import concurrent.futures
import functools
import traceback
from logger import logger
from core.error_handling import handle_error

# ================================
# ThreadPoolExecutor Initialization
# ================================
# Reuse a global thread pool instead of creating threads on each call.
# This improves performance for repeated threaded executions.
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)


def run_in_thread(func, *args, **kwargs):
    """
    Execute a blocking function in a separate thread using the shared thread pool.

    Args:
        func (callable): The function to run in a separate thread.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The return value of the function executed in the separate thread.

    Raises:
        Reraises any exceptions encountered in the threaded execution, wrapped with handle_error.
    """
    try:
        # Create a partial function with provided arguments
        partial_func = functools.partial(func, *args, **kwargs)

        # Submit to executor and wait for result
        future = _executor.submit(partial_func)
        return future.result()

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[THREAD_UTILS_001] ❌ Error in run_in_thread: {e}\n{tb}")
        handle_error(
            e,
            code="THREAD_UTILS_001",
            user_message="Threaded execution failed.",
            raise_it=True
        )


def run_async(coro, *args, **kwargs):
    """
    Utility to run an async coroutine when the caller is not async-aware.

    Behavior:
        - If an event loop is already running, schedule the coroutine and return a Task.
        - If no event loop is running, create one and block until the coroutine completes.

    Args:
        coro (coroutine function): The coroutine function to execute.
        *args: Positional arguments for the coroutine.
        **kwargs: Keyword arguments for the coroutine.

    Returns:
        The result of the coroutine if run in a new event loop, 
        or an asyncio.Task if scheduled in an existing loop.

    Raises:
        Reraises any exceptions encountered, wrapped with handle_error.
    """
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Handle if the event loop is already running
        if loop.is_running():
            return asyncio.ensure_future(coro(*args, **kwargs))
        else:
            return loop.run_until_complete(coro(*args, **kwargs))

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[THREAD_UTILS_002] ❌ Error in run_async: {e}\n{tb}")
        handle_error(
            e,
            code="THREAD_UTILS_002",
            user_message="Async execution failed.",
            raise_it=True
        )
