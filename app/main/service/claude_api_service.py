"""
Claude API integration service.
Handles communication with Claude API for tool selection and execution.
Prepared for future SSE/WebSocket implementation.
"""
import json
from typing import Dict, List, Any, Optional, AsyncGenerator, Type
from datetime import datetime

from sqlalchemy.orm import Session

from app.main.model.tool import Tool, ToolType
from app.main.service.tool_service import execute_tool, get_active_tools


class ClaudeAPIService:
    """
    Service for integrating with Claude API.
    Handles tool selection, execution, and response formatting.
    """

    def __init__(self):
        """Initialize Claude API service"""
        # Future: Add Claude API client initialization here
        pass

    def select_tools_for_query(
            self,
            db: Session,
            query: str,
            available_tools: Optional[List[Tool]] = None
    ) -> list[Type[Tool]]:
        """
        Select appropriate tools based on user query.
        This is a simplified version - future versions will use Claude API.
        """
        if not available_tools:
            available_tools = get_active_tools(db)

        selected_tools = []
        query_lower = query.lower()

        # Simple keyword-based tool selection (to be replaced with Claude API)
        tool_keywords = {
            ToolType.ACTIVITY_ANALYZER: ['activity', 'activities', 'recent', 'what did', 'what happened'],
            ToolType.SLEEP_PATTERN_ANALYZER: ['sleep', 'sleeping', 'nap', 'rest', 'bedtime'],
            ToolType.CARE_METRICS_ANALYZER: ['care', 'caregiver', 'who', 'participation', 'sharing'],
            ToolType.SCHEDULE_ASSISTANT: ['schedule', 'upcoming', 'events', 'appointments', 'when']
        }

        for tool in available_tools:
            tool_type_keywords = tool_keywords.get(tool.tool_type, [])
            if any(keyword in query_lower for keyword in tool_type_keywords):
                selected_tools.append(tool)

        # Default to activity analyzer if no specific match
        if not selected_tools and available_tools:
            activity_tool = next(
                (t for t in available_tools if t.tool_type == ToolType.ACTIVITY_ANALYZER),
                available_tools[0]
            )
            selected_tools.append(activity_tool)

        return selected_tools

    def format_tool_results_for_claude(
            self,
            tool_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format tool execution results for Claude API consumption.
        Structures data in a way that's optimal for Claude's processing.
        """
        formatted_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_executions": len(tool_results),
            "results": []
        }

        for result in tool_results:
            formatted_result = {
                "tool_id": result["tool_id"],
                "tool_name": result["metadata"]["tool_name"],
                "tool_type": result["metadata"]["tool_type"],
                "execution_status": result["status"],
                "data": result["data"],
                "execution_time_ms": result["execution_time_ms"]
            }
            formatted_results["results"].append(formatted_result)

        return formatted_results

    async def process_query_with_tools(
            self,
            db: Session,
            user_id: int,
            query: str,
            baby_id: Optional[int] = None,
            stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a user query using appropriate tools.
        This is the main entry point for Claude API integration.

        Args:
            db: Database session
            user_id: ID of the user making the query
            query: User's natural language query
            baby_id: Optional specific baby ID to filter data
            stream: Whether to stream results (prepared for future SSE/WebSocket)

        Returns:
            Processed results ready for Claude API or direct response
        """
        # Select tools based on query
        selected_tools = self.select_tools_for_query(db, query)

        if not selected_tools:
            return {
                "error": "No suitable tools found for your query",
                "query": query
            }

        # Execute selected tools
        tool_results = []
        for tool in selected_tools:
            try:
                # Prepare parameters based on query (simplified version)
                parameters = self._extract_parameters_from_query(query, tool.tool_type)

                # Execute tool
                result = execute_tool(
                    db,
                    tool.id,
                    user_id,
                    parameters,
                    baby_id
                )
                tool_results.append(result)

            except Exception as e:
                # Log error but continue with other tools
                tool_results.append({
                    "tool_id": tool.id,
                    "status": "error",
                    "error": str(e),
                    "metadata": {
                        "tool_name": tool.name,
                        "tool_type": tool.tool_type
                    }
                })

        # Format results for Claude API
        formatted_results = self.format_tool_results_for_claude(tool_results)

        # Add query context
        formatted_results["query_context"] = {
            "original_query": query,
            "baby_id": baby_id,
            "tools_selected": [t.name for t in selected_tools]
        }

        return formatted_results

    def _extract_parameters_from_query(
            self,
            query: str,
            tool_type: str
    ) -> Dict[str, Any]:
        """
        Extract parameters from query based on tool type.
        This is a simplified version - future versions will use Claude API.
        """
        parameters = {}
        query_lower = query.lower()

        # Extract timeframe
        if 'today' in query_lower:
            parameters['timeframe'] = 'today'
        elif 'week' in query_lower or 'weekly' in query_lower:
            parameters['timeframe'] = 'week'
        elif 'month' in query_lower or 'monthly' in query_lower:
            parameters['timeframe'] = 'month'

        # Extract limit for activities
        if tool_type == ToolType.ACTIVITY_ANALYZER:
            if 'last' in query_lower:
                # Try to extract number
                words = query_lower.split()
                for i, word in enumerate(words):
                    if word == 'last' and i + 1 < len(words):
                        try:
                            limit = int(words[i + 1])
                            parameters['limit'] = limit
                        except ValueError:
                            pass

        # Extract days for sleep analysis
        if tool_type == ToolType.SLEEP_PATTERN_ANALYZER:
            if 'days' in query_lower:
                words = query_lower.split()
                for i, word in enumerate(words):
                    if word == 'days' and i > 0:
                        try:
                            days = int(words[i - 1])
                            parameters['days'] = days
                        except ValueError:
                            pass

        return parameters

    # Prepared for future SSE/WebSocket implementation
    async def stream_query_results(
            self,
            db: Session,
            user_id: int,
            query: str,
            baby_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream query results for real-time updates.
        Prepared for future SSE/WebSocket implementation.
        """
        # Initial response
        yield json.dumps({
            "type": "start",
            "message": "Processing your query..."
        })

        # Tool selection
        selected_tools = self.select_tools_for_query(db, query)
        yield json.dumps({
            "type": "tools_selected",
            "tools": [t.name for t in selected_tools]
        })

        # Execute tools and stream results
        for tool in selected_tools:
            yield json.dumps({
                "type": "tool_executing",
                "tool": tool.name
            })

            try:
                parameters = self._extract_parameters_from_query(query, tool.tool_type)
                result = execute_tool(db, tool.id, user_id, parameters, baby_id)

                yield json.dumps({
                    "type": "tool_result",
                    "tool": tool.name,
                    "result": result
                })
            except Exception as e:
                yield json.dumps({
                    "type": "tool_error",
                    "tool": tool.name,
                    "error": str(e)
                })

        # Final response
        yield json.dumps({
            "type": "complete",
            "message": "Query processing complete"
        })