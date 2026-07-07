import asyncio
import logging
import re
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.agent.tool_registry import ToolRegistry
from app.agent.llm_interface import OllamaLLM
from app.agent.llm_interface import AzureOpenAILLM
from app.memory.memory_handler import MemoryHandler

logger = logging.getLogger(__name__)


class AgentLoop:
    def __init__(self):
        self.tools = ToolRegistry()
        self.llm = AzureOpenAILLM()
        self.memory = MemoryHandler()
        self.max_iterations = settings.agent_max_iterations

    async def run(self, session_id: str, user_prompt: str, history: List[Dict[str, Any]]) -> Tuple[str, List[Dict]]:
        """Multi-stage agent: repeatedly call tools as needed, always use 'name' in tool_history."""
        await self.memory.save_user_message(session_id, user_prompt)
        tool_history = []

        # Retrieve context and build history string
        context = await self.memory.retrieve(session_id, history)
        logger.info(f"[Session {session_id[:8]}] Memory context length: {len(context)}, history items: {len(history)}")
        logger.info(f"[Session {session_id[:8]}] Context preview: {context[:300]}")
        history_str = ""
        for msg in history[-5:]:  # Last 5 messages for context
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]
            history_str += f"{role}: {content}\n"

        # Multi-stage loop: keep original user_prompt, accumulate results
        accumulated_results = []
        used_tool_calls = set()  # Track tool+args to prevent duplicates
        max_steps = 5
        for step in range(max_steps):
            # Build tool results context from previous steps
            results_context = ""
            if accumulated_results:
                results_context = "\n\nInformation gathered so far:\n" + "\n---\n".join(accumulated_results)

            tools_list = "\n".join([f"- {t}" for t in self.tools.list_tools()])
            tool_prompt = f"""You are Aether, an AI agent. You MUST use tools when needed.

Available tools:
{tools_list}

Tool descriptions:
- web_search: Search the internet for current information, news, facts, scores, events.
- web_crawl: Fetch and read the full content of a specific URL.
- sql_query: Run a SQL query against the database.
- api_call: Call an external REST API endpoint.
- python_exec: Execute Python code for calculations, data processing, math, conversions, string manipulation, or any computation. Use this whenever the user asks you to calculate, compute, convert, or process something.

Previous conversation:
{history_str}

Long-term context:
{context}

User question: {user_prompt}{results_context}

Rules:
1. If you have enough information from the gathered results above to answer the user's question, respond with the final answer directly. No JSON, no tool calls.
2. If you still need more information OR the user asks for a calculation/computation, respond with EXACTLY one line:
   tool_name: {{\"<arg>\": \"<value>\"}}
   Examples:
   web_search: {{\"query\": \"latest football scores\"}}
   web_crawl: {{\"url\": \"https://example.com\"}}
   sql_query: {{\"query\": \"SELECT * FROM users\"}}
   api_call: {{\"url\": \"https://api.example.com/data\", \"method\": \"GET\"}}
   python_exec: {{\"code\": \"print(2**10)\"}}
3. Do NOT call the same tool twice with the same arguments.
4. Do NOT output JSON to the user, only use it for tool invocation.
5. For ANY math, calculation, or code request, ALWAYS use python_exec.
"""
            tool_response = await self.llm.generate(tool_prompt)
            logger.info(f"[Step {step}] LLM raw response:\n{tool_response[:500]}")
            tool_call = self.tools.parse_tool_call(tool_response)
            logger.info(f"[Step {step}] Parsed tool_call: {tool_call}")

            if tool_call and tool_call["name"] in self.tools.available_tools:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})

                # Prevent duplicate tool calls with same args
                import json
                call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                if call_key in used_tool_calls:
                    logger.warning(f"[Step {step}] Duplicate tool call blocked: {tool_name}")
                    # Force LLM to answer with what we have
                    break
                used_tool_calls.add(call_key)

                try:
                    # --- Specialized handling for each tool ---
                    output = await self.tools.invoke(tool_call)
                    logger.info(f"[Step {step}] Tool {tool_name} output: {str(output)[:300]}")
                    tool_history.append({"name": tool_name, "args": tool_args})
                    await self.memory.save_tool_result(session_id, tool_call, output)

                    if tool_name == "web_search":
                        # Also crawl top URLs for deeper context
                        crawl_texts = []
                        for item in output.get("results", [])[:3]:
                            url = item.get("url")
                            if url:
                                crawl_result = await self.tools.available_tools["web_crawl"](url)
                                if crawl_result.get("content"):
                                    crawl_texts.append(f"[{url}]:\n{crawl_result['content'][:800]}")
                        search_summary = f"Web search for '{tool_args.get('query', '')}' returned:\n"
                        for r in output.get("results", []):
                            search_summary += f"- {r.get('title', '')}: {r.get('url', '')}\n"
                        if crawl_texts:
                            search_summary += "\nPage contents:\n" + "\n".join(crawl_texts)
                        accumulated_results.append(search_summary)
                    elif tool_name == "web_crawl":
                        accumulated_results.append(f"Crawled {tool_args.get('url', '')}:\n{output.get('content', str(output))[:1500]}")
                    elif tool_name == "sql_query":
                        accumulated_results.append(f"SQL result for '{tool_args.get('query', '')}':\n{output}")
                    elif tool_name == "api_call":
                        accumulated_results.append(f"API response from {tool_args.get('url', '')}:\n{output}")
                    elif tool_name == "python_exec":
                        accumulated_results.append(f"Python execution output:\nstdout: {output.get('stdout', '')}\nstderr: {output.get('stderr', '')}")
                    else:
                        accumulated_results.append(f"{tool_name} result:\n{output}")
                    # Loop back to check if another tool is needed or if we can answer
                    continue
                except Exception as e:
                    error_msg = f"Tool {tool_name} failed: {str(e)}"
                    tool_history.append({
                        "name": tool_name,
                        "args": tool_args
                    })
                    await self.memory.save_tool_result(session_id, tool_call, {"error": str(e)})
                    # On error, break and return error
                    await self.memory.save_final_response(session_id, error_msg)
                    return error_msg, tool_history
            else:
                # No tool call: LLM either answered directly or has enough info
                # If the LLM gave a real answer (not a tool call), use it as-is
                # But if we have accumulated results, generate a final natural answer
                if accumulated_results:
                    results_context = "\n\n".join(accumulated_results)
                    answer_prompt = f"""You are Aether. Using ONLY the information below, write a concise, natural answer to the user's question. Do NOT mention tool calls, JSON, or your reasoning process.

User question: {user_prompt}

Information gathered:
{results_context}

Answer:"""
                    final_response = await self.llm.generate(answer_prompt)
                else:
                    final_response = tool_response  # LLM answered directly
                await self.memory.save_final_response(session_id, final_response)
                return final_response, tool_history
        # Max steps: still generate best-effort answer from accumulated results
        if accumulated_results:
            results_context = "\n\n".join(accumulated_results)
            answer_prompt = f"""You are Aether. Using the information below, write the best answer you can to the user's question. Do NOT mention tool calls or reasoning.

User question: {user_prompt}

Information gathered:
{results_context}

Answer:"""
            final_response = await self.llm.generate(answer_prompt)
            await self.memory.save_final_response(session_id, final_response)
            return final_response, tool_history
        final_msg = "I was unable to find an answer after several attempts."
        await self.memory.save_final_response(session_id, final_msg)
        return final_msg, tool_history

    def _build_prompt(self, user_prompt: str, context: str, history: List[Dict]) -> str:
        """Build agent prompt with tools and context."""
        tools_list = "\n".join([f"- {t}" for t in self.tools.list_tools()])
        
        history_str = ""
        for msg in history[-5:]:  # Last 5 messages for context
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]
            history_str += f"{role}: {content}\n"

        prompt = f"""You are Aether, an AI agent that can use external tools to answer questions.

Available tools:
{tools_list}

Previous conversation:
{history_str}

Long-term context:
{context}

User query: {user_prompt}

Rules:
1. If you need to use a tool, respond with EXACTLY one line containing the tool call in JSON format:
   tool_name: {{\"<arg>\": \"<value>\", ...}}
   Do NOT include any other text, explanations, or natural language.
2. Examples of tool calls:
   web_search: {{\"query\": \"latest football scores\"}}
   web_crawl: {{\"url\": \"https://example.com\"}}
   sql_query: {{\"query\": \"SELECT * FROM users\"}}
   api_call: {{\"url\": \"https://api.example.com/data\", \"method\": \"GET\"}}
   python_exec: {{\"code\": \"print('hello')\"}}
3. If you already have enough information to answer the user's question, DO NOT call another tool. Only call a tool if it is absolutely necessary to answer the user's question.
4. If no tool is needed, provide the final answer directly, with no JSON or tool call.
5. Be concise and use real data from tools.
6. Do NOT explain your reasoning or output JSON to the user, only use it for tool invocation.
"""
        
        return prompt
