import asyncpg
from app.config import settings
from typing import Dict, Any, List


async def sql_query(query: str) -> Dict[str, Any]:
    """Execute any SQL statement against the database.

    - SELECT: returns rows and count
    - Other statements (INSERT/UPDATE/DELETE/DDL): returns command status
    """
    try:
        q = query.strip()
        q_upper = q.upper()

        # Connect to database (asyncpg expects a normal postgresql:// URL)
        db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        try:
            conn = await asyncpg.connect(db_url, timeout=10)
        except Exception as e:
            return {"error": f"Could not connect to database: {str(e)}"}

        try:
            if q_upper.startswith("SELECT"):
                rows = await conn.fetch(q, timeout=30)
                result = [dict(row) for row in rows]
                return {"rows": result, "count": len(result)}
            else:
                # For non-SELECT queries, use execute() which returns a command status string
                status = await conn.execute(q, timeout=30)
                return {"status": status}
        finally:
            await conn.close()

    except Exception as e:
        return {"error": f"Query execution failed: {str(e)}"}
