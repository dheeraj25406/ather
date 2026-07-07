import logging
import time
from typing import Any, Callable
from functools import wraps
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("aether")


def log_agent_query(session_id: str, query: str, duration: float, tools_used: int, success: bool):
    """Log an agent query."""
    logger.info(
        f"Agent Query | Session: {session_id[:12]} | Duration: {duration:.2f}s | Tools: {tools_used} | Success: {success}",
        extra={
            "session_id": session_id,
            "query_length": len(query),
            "duration": duration,
            "tools_used": tools_used,
            "success": success
        }
    )


def log_tool_call(tool_name: str, args: dict, error: str = None, duration: float = 0):
    """Log a tool call."""
    status = "error" if error else "success"
    logger.info(
        f"Tool Call | Tool: {tool_name} | Status: {status} | Duration: {duration:.2f}s",
        extra={
            "tool_name": tool_name,
            "status": status,
            "error": error,
            "duration": duration,
            "args_keys": list(args.keys())
        }
    )


def log_memory_operation(operation: str, session_id: str, data_size: int = 0):
    """Log memory operations."""
    logger.debug(
        f"Memory | Operation: {operation} | Session: {session_id[:12]} | Size: {data_size}",
        extra={
            "operation": operation,
            "session_id": session_id,
            "data_size": data_size
        }
    )


def timing_decorator(func: Callable) -> Callable:
    """Decorator to log function execution time."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start
            logger.debug(f"Function {func.__name__} took {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"Function {func.__name__} failed after {duration:.3f}s: {str(e)}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.debug(f"Function {func.__name__} took {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"Function {func.__name__} failed after {duration:.3f}s: {str(e)}")
            raise
    
    # Return async wrapper if function is async
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class MetricsCollector:
    """Collect metrics for monitoring."""
    
    def __init__(self):
        self.queries_total = 0
        self.queries_success = 0
        self.queries_failed = 0
        self.tools_total = 0
        self.tools_success = 0
        self.tools_failed = 0
        self.total_duration = 0.0
        self.sessions_active = set()
    
    def record_query(self, session_id: str, success: bool, duration: float):
        """Record query metric."""
        self.queries_total += 1
        if success:
            self.queries_success += 1
        else:
            self.queries_failed += 1
        self.total_duration += duration
        self.sessions_active.add(session_id)
    
    def record_tool_call(self, success: bool):
        """Record tool call metric."""
        self.tools_total += 1
        if success:
            self.tools_success += 1
        else:
            self.tools_failed += 1
    
    def get_metrics(self) -> dict:
        """Get collected metrics."""
        avg_duration = self.total_duration / max(self.queries_total, 1)
        return {
            "queries_total": self.queries_total,
            "queries_success": self.queries_success,
            "queries_failed": self.queries_failed,
            "success_rate": (self.queries_success / max(self.queries_total, 1)) * 100,
            "tools_total": self.tools_total,
            "tools_success": self.tools_success,
            "tools_failed": self.tools_failed,
            "tool_success_rate": (self.tools_success / max(self.tools_total, 1)) * 100,
            "avg_query_duration": avg_duration,
            "active_sessions": len(self.sessions_active),
            "timestamp": datetime.utcnow().isoformat()
        }


# Global metrics instance
metrics = MetricsCollector()
