import logging
from typing import Dict, Any, Optional
from .tools.web_search import web_search
from .tools.sql_executor import sql_query
from .tools.python_executor import run_python
from .tools.api_caller import call_api
from .tools.web_crawl import web_crawl

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self.available_tools = {
            "web_search": web_search,
            "web_crawl": web_crawl,
            "sql_query": sql_query,
            "python_exec": run_python,
            "api_call": call_api,
        }

    def list_tools(self):
        return list(self.available_tools.keys())

    def parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        import re
        import json

        stripped = text.strip()
        if not stripped:
            return None

        # 1. Extract python code from markdown code blocks:
        #    python_exec: ```python\n...\n``` or ```\n...\n```
        code_block_match = re.search(
            r'python_exec\s*[:=]\s*```(?:python)?\s*\n(.*?)```',
            stripped, re.DOTALL | re.IGNORECASE
        )
        if code_block_match:
            code = code_block_match.group(1).strip()
            logger.info(f"Parsed python_exec from code block ({len(code)} chars)")
            return {"name": "python_exec", "args": {"code": code}}

        # 2. Standalone code block after mentioning python_exec
        if "python_exec" in stripped.lower():
            standalone_block = re.search(r'```(?:python)?\s*\n(.*?)```', stripped, re.DOTALL)
            if standalone_block:
                code = standalone_block.group(1).strip()
                logger.info(f"Parsed python_exec from standalone code block ({len(code)} chars)")
                return {"name": "python_exec", "args": {"code": code}}

        # 3. Standard single-line format: tool_name: {"arg": "value"}
        for raw_line in stripped.splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue

            name, argstr = line.split(":", 1)
            name = name.strip()
            argstr = argstr.strip()

            if name == "TOOL_NAME":
                m = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)", argstr)
                if m:
                    name = m.group(1)
                    argstr = m.group(2).strip()

            if name in self.available_tools:
                return self._parse_args(name, argstr)

        # 4. Function-style: tool_name({...})
        for raw_line in stripped.splitlines():
            line = raw_line.strip()
            m = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.+)\)$", line)
            if m:
                name = m.group(1)
                argstr = m.group(2).strip()
                if name in self.available_tools:
                    return self._parse_args(name, argstr)

        # 5. Multi-line JSON: tool_name: { ... } spanning multiple lines
        multiline_match = re.search(
            r'((?:' + '|'.join(re.escape(t) for t in self.available_tools) + r'))\s*:\s*(\{)',
            stripped,
        )
        if multiline_match:
            name = multiline_match.group(1)
            start = multiline_match.start(2)
            # Find matching closing brace
            depth = 0
            for i in range(start, len(stripped)):
                if stripped[i] == '{':
                    depth += 1
                elif stripped[i] == '}':
                    depth -= 1
                    if depth == 0:
                        argstr = stripped[start:i+1]
                        return self._parse_args(name, argstr)

        # 6. Fallback: tool_name({...}) anywhere in text
        m = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\((\{.*\})\)", stripped, re.DOTALL)
        if m:
            name = m.group(1)
            argstr = m.group(2)
            if name in self.available_tools:
                logger.info(f"Parsed tool call via fallback regex: {name}")
                return self._parse_args(name, argstr)

        # 7. Auto-detect: standalone Python code block without explicit tool mention
        #    If the LLM just outputs code in a ```python block, treat it as python_exec
        standalone_code = re.search(r'```(?:python)?\s*\n(.*?)```', stripped, re.DOTALL)
        if standalone_code:
            code = standalone_code.group(1).strip()
            if code and any(kw in code for kw in ('import ', 'print(', 'def ', 'for ', 'while ', '=', 'return ')):
                logger.info(f"Auto-detected standalone code block as python_exec ({len(code)} chars)")
                return {"name": "python_exec", "args": {"code": code}}

        logger.debug(f"No tool call found in response ({len(stripped)} chars)")
        return None

    # Map tool names to their primary argument name for fallback parsing
    DEFAULT_ARG_KEYS = {
        "web_search": "query",
        "web_crawl": "url",
        "sql_query": "query",
        "python_exec": "code",
        "api_call": "url",
    }

    def _parse_args(self, name: str, argstr: str) -> Dict[str, Any]:
        args = {}
        import json
        import ast
        try:
            args = json.loads(argstr)
        except Exception:
            try:
                parsed = ast.literal_eval(argstr)
                if isinstance(parsed, dict):
                    args = parsed
                else:
                    default_key = self.DEFAULT_ARG_KEYS.get(name, "query")
                    args = {default_key: str(parsed)}
            except Exception:
                # If it is plain text, use the tool's primary argument
                cleaned = argstr.strip().strip('"')
                if cleaned:
                    default_key = self.DEFAULT_ARG_KEYS.get(name, "query")
                    args = {default_key: cleaned}
                else:
                    args = {}
        return {"name": name, "args": args}

    async def invoke(self, tool_call: Dict[str, Any]) -> Any:
        name = tool_call.get("name")
        args = tool_call.get("args", {})
        tool = self.available_tools.get(name)
        if not tool:
            logger.error(f"Tool '{name}' not found in registry")
            raise ValueError(f"Tool {name} is not available")
        logger.info(f"Invoking tool '{name}' with args keys: {list(args.keys())}")
        result = await tool(**args)
        logger.info(f"Tool '{name}' completed, result type: {type(result).__name__}, size: {len(str(result))} chars")
        return result
