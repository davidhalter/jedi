try:
    from queue import Queue
except ImportError:
    # Python 2 shim
    from Queue import Queue

stop_execution_signal_queue = Queue(maxsize=1)
"""
Allows a controller thread to cause Jedi to abort execution.
`ExecutionRecursionDetector.push_execution` will raise `StopExecutionException`
if the `stop_execution_signal_queue` is not empty.
"""

class StopExecutionException(Exception):
    """Raised when Jedi aborts execution"""
    pass


def poll_and_handle_stop_execution_signal():
    if not stop_execution_signal_queue.empty():
        stop_execution_signal_queue.get()
        raise StopExecutionException('Received signal to stop execution.')

def poll_and_handle_stop_execution_signal_at_start(function):
    def wrapper(obj, *args, **kwargs):
        poll_and_handle_stop_execution_signal()
        return function(obj, *args, **kwargs)
    return wrapper
