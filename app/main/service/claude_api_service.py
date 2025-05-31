"""
Claude API integration service.
Handles communication with Claude API for tool selection and execution.
Prepared for future SSE/WebSocket implementation.
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Union

from anthropic import Anthropic
from sqlalchemy.orm import Session, InstrumentedAttribute

from app.main.model.query import ClaudeAPIConfig, QueryProcessingResult, ToolSelectionResult, ToolExecutionInfo, \
    ExecutionStatus, ToolSelectionInfo, QueryType
from app.main.model.tool import Tool, ToolType
from app.main.service.tool_service import execute_tool, get_active_tools

logger = logging.getLogger(__name__)

class ClaudeAPIService:
    """
    Service for integrating with Claude API.
    Handles tool selection, execution, and response formatting.
    """

    def __init__(
            self,
            api_key: str,
            config: Optional[ClaudeAPIConfig] = None
    ):
        self.client = Anthropic(api_key=api_key)
        self.config = config or ClaudeAPIConfig()

    async def process_query_with_tools(
            self,
            db: Session,
            user_id: int,
            query: str,
            baby_id: Optional[int] = None,
            stream: bool = False,
            include_thinking: bool = False
    ) -> QueryProcessingResult:
        """
        Enhanced query processing using structured schemas.
        """
        global parameters, processing_metadata
        start_time = time.time()

        try:
            # Initialize processing metadata
            processing_metadata = {
                "query": query,
                "baby_id": baby_id,
                "user_id": user_id,
                "stream_enabled": stream,
                "include_thinking": include_thinking,
                "start_time": start_time,
                "phases": {}
            }

            # Phase 1: Get available tools
            phase_start = time.time()
            available_tools = get_active_tools(db)
            processing_metadata["phases"]["tool_discovery"] = {
                "duration_ms": (time.time() - phase_start) * 1000,
                "tools_found": len(available_tools)
            }

            if not available_tools:
                return QueryProcessingResult(
                    success=False,
                    data={},
                    tool_selection=ToolSelectionResult(
                        selected_tools=[],
                        tool_info=[],
                        reasoning="No active tools available",
                        confidence=0.0,
                        fallback_used=True
                    ),
                    execution_summary={},
                    processing_metadata=processing_metadata,
                    error="No active tools available"
                )

            # Phase 2: Tool selection using Claude
            phase_start = time.time()
            tool_selection_result = await self.select_tools_for_query(
                db, query, available_tools, baby_id, include_thinking
            )
            processing_metadata["phases"]["tool_selection"] = {
                "duration_ms": (time.time() - phase_start) * 1000,
                "tools_selected": len(tool_selection_result.selected_tools),
                "confidence": tool_selection_result.confidence,
                "fallback_used": tool_selection_result.fallback_used
            }

            if not tool_selection_result.selected_tools:
                return QueryProcessingResult(
                    success=False,
                    data={},
                    tool_selection=tool_selection_result,
                    execution_summary={},
                    processing_metadata=processing_metadata,
                    error="No suitable tools found for your query"
                )

            # Phase 3: Tool execution
            phase_start = time.time()
            tool_results = []
            execution_info = []

            for i, tool in enumerate(tool_selection_result.selected_tools):
                execution_start = time.time()

                try:
                    # Extract parameters using Claude
                    parameters = await self._extract_parameters_from_query(
                        query, tool.tool_type, baby_id
                    )

                    # Execute tool
                    result = execute_tool(db, tool.id, user_id, parameters, baby_id)
                    tool_results.append(result)

                    # Track execution info
                    execution_info.append(ToolExecutionInfo(
                        tool_id=tool.id,
                        tool_name=tool.name,
                        tool_type=tool.tool_type,
                        status=ExecutionStatus.SUCCESS,
                        execution_time_ms=(time.time() - execution_start) * 1000,
                        result_count=len(result.get("data", [])) if isinstance(result.get("data"), list) else 1,
                        parameters_used=parameters
                    ))

                except Exception as e:
                    logger.error(f"Tool execution failed for {tool.name}: {str(e)}")

                    error_result = {
                        "tool_id": tool.id,
                        "status": "error",
                        "error": str(e),
                        "metadata": {
                            "tool_name": tool.name,
                            "tool_type": tool.tool_type
                        }
                    }
                    tool_results.append(error_result)

                    execution_info.append(ToolExecutionInfo(
                        tool_id=tool.id,
                        tool_name=tool.name,
                        tool_type=tool.tool_type,
                        status=ExecutionStatus.FAILED,
                        execution_time_ms=(time.time() - execution_start) * 1000,
                        error_message=str(e),
                        parameters_used=parameters
                    ))

            processing_metadata["phases"]["tool_execution"] = {
                "duration_ms": (time.time() - phase_start) * 1000,
                "total_executions": len(execution_info),
                "successful_executions": len([e for e in execution_info if e.status == ExecutionStatus.SUCCESS]),
                "failed_executions": len([e for e in execution_info if e.status == ExecutionStatus.FAILED])
            }

            # Phase 4: Result synthesis
            phase_start = time.time()
            formatted_results = await self.format_tool_results_for_claude(
                tool_results, query, tool_selection_result.reasoning
            )
            processing_metadata["phases"]["result_synthesis"] = {
                "duration_ms": (time.time() - phase_start) * 1000
            }

            # Create execution summary
            execution_summary = {
                "total_tools": len(tool_selection_result.selected_tools),
                "successful_executions": len([e for e in execution_info if e.status == ExecutionStatus.SUCCESS]),
                "failed_executions": len([e for e in execution_info if e.status == ExecutionStatus.FAILED]),
                "execution_details": [info.__dict__ for info in execution_info],
                "total_execution_time_ms": sum(info.execution_time_ms or 0 for info in execution_info)
            }

            total_processing_time = (time.time() - start_time) * 1000
            processing_metadata["total_processing_time_ms"] = total_processing_time

            return QueryProcessingResult(
                success=True,
                data=formatted_results,
                tool_selection=tool_selection_result,
                execution_summary=execution_summary,
                processing_metadata=processing_metadata,
                total_processing_time_ms=total_processing_time
            )

        except Exception as e:
            logger.error(f"Query processing failed: {str(e)}")

            error_processing_time = (time.time() - start_time) * 1000
            processing_metadata["total_processing_time_ms"] = error_processing_time
            processing_metadata["error_phase"] = "unknown"

            return QueryProcessingResult(
                success=False,
                data={},
                tool_selection=ToolSelectionResult(
                    selected_tools=[],
                    tool_info=[],
                    reasoning=f"Processing error: {str(e)}",
                    confidence=0.0,
                    fallback_used=True
                ),
                execution_summary={},
                processing_metadata=processing_metadata,
                error=str(e),
                total_processing_time_ms=error_processing_time
            )

    async def select_tools_for_query(
            self,
            db: Session,
            query: str,
            available_tools: Optional[List[Type[Tool]]] = None,
            baby_id: Optional[int] = None,
            include_thinking: bool = False
    ) -> ToolSelectionResult:
        """
        Enhanced tool selection using structured schemas.
        """
        selection_start = time.time()

        if not available_tools:
            available_tools = get_active_tools(db)

        if not available_tools:
            return ToolSelectionResult(
                selected_tools=[],
                tool_info=[],
                reasoning="No active tools available",
                confidence=0.0,
                fallback_used=True,
                selection_time_ms=(time.time() - selection_start) * 1000
            )

        # Prepare tool descriptions for Claude
        tool_descriptions = self._prepare_tool_descriptions(available_tools)

        # Create comprehensive prompt for tool selection
        prompt = self._create_tool_selection_prompt(query, tool_descriptions, baby_id)

        try:
            # Use Claude with thinking based on parameter
            # Build the base parameters
            params = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [{
                    "role": "user",
                    "content": prompt
                }]
            }

            # Only add thinking parameter when needed
            if include_thinking:
                params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.config.thinking_budget_tokens
                }

            response = self.client.messages.create(**params)

            # Extract thinking process and response content properly
            thinking_process = None
            response_content = ""

            if response.content:
                # Separate thinking blocks from text content blocks
                for block in response.content:
                    if hasattr(block, 'type'):
                        if block.type == 'thinking':
                            # Extract thinking content
                            if thinking_process is None:
                                thinking_process = []
                            thinking_process.append(block.content if hasattr(block, 'content') else str(block))
                        elif block.type == 'text':
                            # Extract text content
                            response_content += block.text
                    else:
                        # Fallback: if no type attribute, assume it's text content
                        if hasattr(block, 'text'):
                            response_content += block.text

            # Convert thinking_process list to string if it exists
            if thinking_process:
                thinking_process = "\n".join(thinking_process)

            # Extract structured response
            selected_tools, tool_info, reasoning, confidence, query_classification = self._parse_tool_selection_response(
                response_content, available_tools
            )

            selection_time = (time.time() - selection_start) * 1000

            return ToolSelectionResult(
                selected_tools=selected_tools,
                tool_info=tool_info,
                reasoning=reasoning,
                confidence=confidence,
                query_classification=query_classification,
                thinking_process=thinking_process,
                fallback_used=False,
                selection_time_ms=selection_time
            )

        except Exception as e:
            logger.error(f"Claude tool selection failed: {str(e)}")

            # Fallback to keyword-based selection
            fallback_tools = self._fallback_tool_selection(query, available_tools)
            fallback_tool_info = [
                ToolSelectionInfo(
                    tool_id=tool.id,
                    tool_name=tool.name,
                    tool_type=tool.tool_type,
                    relevance_score=0.5,
                    selection_reason="Fallback keyword matching"
                ) for tool in fallback_tools
            ]

            selection_time = (time.time() - selection_start) * 1000

            return ToolSelectionResult(
                selected_tools=fallback_tools,
                tool_info=fallback_tool_info,
                reasoning=f"Used fallback selection due to API error: {str(e)}",
                confidence=0.5,
                fallback_used=True,
                selection_time_ms=selection_time
            )

    def _parse_tool_selection_response(
            self,
            response_content: str,
            available_tools: List[Type[Tool]]
    ) -> Union[tuple[list[Type[Tool]], list[ToolSelectionInfo], Any, float, Optional[QueryType]], tuple[
        list[Union[Type[Tool], Any]], list[ToolSelectionInfo], str, float, QueryType]]:
        """Enhanced parsing with structured tool information"""

        try:
            # Extract JSON from response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = response_content[json_start:json_end]
            parsed_response = json.loads(json_str)

            # Extract selected tools and create detailed info
            selected_tools = []
            tool_info = []
            tool_dict = {tool.name: tool for tool in available_tools}

            for selected_tool_data in parsed_response.get("selected_tools", []):
                tool_name = selected_tool_data.get("tool_name")
                if tool_name in tool_dict:
                    tool = tool_dict[tool_name]
                    selected_tools.append(tool)

                    # Create detailed tool info
                    tool_info.append(ToolSelectionInfo(
                        tool_id=tool.id,
                        tool_name=tool.name,
                        tool_type=tool.tool_type,
                        relevance_score=selected_tool_data.get("relevance_score", 0.8),
                        selection_reason=selected_tool_data.get("reason", "Selected for query relevance")
                    ))

            reasoning = parsed_response.get("overall_reasoning", "Tool selection completed")
            confidence = float(parsed_response.get("overall_confidence", 0.8))

            # Parse query classification if present
            query_classification = None
            classification_str = parsed_response.get("query_classification")
            if classification_str:
                try:
                    query_classification = QueryType(classification_str.lower())
                except ValueError:
                    query_classification = QueryType.GENERAL_QUESTION

            return selected_tools, tool_info, reasoning, confidence, query_classification

        except Exception as e:
            logger.error(f"Failed to parse tool selection response: {str(e)}")

            # Fallback parsing - look for tool names in text
            selected_tools = []
            tool_info = []

            for tool in available_tools:
                if tool.name.lower() in response_content.lower():
                    selected_tools.append(tool)
                    tool_info.append(ToolSelectionInfo(
                        tool_id=tool.id,
                        tool_name=tool.name,
                        tool_type=tool.tool_type,
                        relevance_score=0.6,
                        selection_reason="Fallback text matching"
                    ))

            if not selected_tools:
                # Default to first available tool
                tool = available_tools[0]
                selected_tools.append(tool)
                tool_info.append(ToolSelectionInfo(
                    tool_id=tool.id,
                    tool_name=tool.name,
                    tool_type=tool.tool_type,
                    relevance_score=0.5,
                    selection_reason="Default fallback selection"
                ))

            return (
                selected_tools,
                tool_info,
                f"Fallback parsing used: {str(e)}",
                0.6,
                QueryType.GENERAL_QUESTION
            )

    def _prepare_tool_descriptions(self, tools: List[Type[Tool]]) -> dict[
        InstrumentedAttribute, dict[str, Union[Union[InstrumentedAttribute, str], Any]]]:
        """Prepare detailed tool descriptions for Claude"""
        descriptions = {}

        # descriptions for each tool type
        tool_type_info = {
            ToolType.ACTIVITY_ANALYZER: {
                "description": "Analyzes baby activities, recent events, and daily patterns",
                "use_cases": "Questions about what the baby did, recent activities, daily summaries",
                "sample_queries": ["What did my baby do today?", "Show recent activities", "Baby's daily summary"],
                "data_types": ["activities", "events", "routines"]
            },
            ToolType.SLEEP_PATTERN_ANALYZER: {
                "description": "Analyzes sleep patterns, nap schedules, and sleep quality metrics",
                "use_cases": "Sleep-related questions, nap analysis, sleep quality assessment",
                "sample_queries": ["How did my baby sleep?", "Sleep patterns this week", "Nap schedule analysis"],
                "data_types": ["sleep_sessions", "nap_times", "sleep_quality"]
            },
            ToolType.FEEDING_TRACKER: {
                "description": "Tracks feeding sessions, nutrition intake, and feeding patterns",
                "use_cases": "Feeding-related questions, nutrition analysis, feeding schedule",
                "sample_queries": ["When did my baby last eat?", "Feeding patterns", "Nutrition summary"],
                "data_types": ["feeding_sessions", "nutrition_data", "feeding_schedule"]
            },
            ToolType.HEALTH_MONITOR: {
                "description": "Monitors health metrics, symptoms, and medical information",
                "use_cases": "Health-related questions, symptom tracking, medical appointments",
                "sample_queries": ["How is my baby's health?", "Recent symptoms", "Medical updates"],
                "data_types": ["health_metrics", "symptoms", "medical_records"]
            },
            ToolType.GROWTH_TRACKER: {
                "description": "Tracks physical growth, weight, height, and development metrics",
                "use_cases": "Growth-related questions, development tracking, milestone progress",
                "sample_queries": ["How is my baby growing?", "Weight progression", "Growth milestones"],
                "data_types": ["growth_measurements", "weight_data", "height_data"]
            },
            ToolType.MILESTONE_TRACKER: {
                "description": "Tracks developmental milestones and achievements",
                "use_cases": "Milestone questions, development progress, achievement tracking",
                "sample_queries": ["What milestones has my baby reached?", "Development progress",
                                   "Recent achievements"],
                "data_types": ["milestones", "achievements", "development_stages"]
            },
            ToolType.CARE_METRICS_ANALYZER: {
                "description": "Analyzes caregiving metrics, caregiver participation, and care distribution",
                "use_cases": "Questions about who provided care, caregiver statistics, care sharing",
                "sample_queries": ["Who took care of the baby?", "Caregiver participation",
                                   "Care sharing analysis"],
                "data_types": ["caregiver_activities", "care_sessions", "participation_metrics"]
            },
            ToolType.SCHEDULE_ASSISTANT: {
                "description": "Manages schedules, upcoming events, and appointment planning",
                "use_cases": "Scheduling questions, upcoming events, appointment management",
                "sample_queries": ["What's scheduled next?", "Upcoming appointments", "Schedule planning"],
                "data_types": ["schedules", "appointments", "events"]
            }
        }

        for tool in tools:
            if tool.tool_type in tool_type_info:
                info = tool_type_info[tool.tool_type]
                descriptions[tool.name] = {
                    "id": str(tool.id),
                    "type": tool.tool_type.value,
                    "description": info["description"],
                    "use_cases": info["use_cases"],
                    "sample_queries": info["sample_queries"],
                    "data_types": info["data_types"],
                    "status": "active" if tool.is_active else "inactive",
                    "version": tool.version,
                    "capabilities": tool.capabilities
                }

        return descriptions

    def _create_tool_selection_prompt(
            self,
            query: str,
            tool_descriptions: Dict[str, Dict[str, str]],
            baby_id: Optional[int]
    ) -> str:
        """Create a comprehensive prompt for Claude to select appropriate tools"""

        tools_json = json.dumps(tool_descriptions, indent=2)
        baby_context = f"for baby ID {baby_id}" if baby_id else "for any baby in the user's account"

        return f"""You are an intelligent assistant for a baby care application. Your task is to analyze user queries and select the most appropriate tools to answer them.

USER QUERY: "{query}"
CONTEXT: This query is {baby_context}

AVAILABLE TOOLS:
{tools_json}

INSTRUCTIONS:
1. Analyze the user's query carefully to understand the intent
2. Consider keywords, context, and implied needs
3. Select 1-{self.config.max_tools_per_query} most relevant tools (avoid over-selection)
4. Provide detailed reasoning for each selection
5. Assign relevance scores (0.0-1.0) for each selected tool
6. Classify the overall query type
7. Assign overall confidence score (0.0-1.0)

RESPONSE FORMAT:
Provide your response as a JSON object with this exact structure:
{{
    "selected_tools": [
        {{
            "tool_name": "exact_tool_name_from_available_tools",
            "tool_type": "tool_type_value",
            "relevance_score": 0.0-1.0,
            "reason": "detailed explanation for selecting this tool"
        }}
    ],
    "overall_reasoning": "comprehensive explanation of your selection logic and how tools work together",
    "overall_confidence": 0.0-1.0,
    "query_classification": "activity_inquiry|sleep_analysis|care_metrics|health_check|schedule_query|general_question|comparative_analysis"
}}

SELECTION GUIDELINES:
- Prioritize tools that directly address the query intent
- Consider temporal aspects (recent, today, this week, etc.)
- For ambiguous queries, select the most commonly needed tool
- Avoid selecting too many tools unless truly necessary for comprehensive analysis
- If no tools are perfectly relevant, select the closest match
- Consider complementary tools for complex queries (e.g., sleep + activities for behavioral analysis)
- Use confidence threshold: only select tools with relevance_score >= {self.config.selection_confidence_threshold}

Analyze the query and provide your tool selection in the specified JSON format."""

    async def _extract_parameters_from_query(
            self,
            query: str,
            tool_type: ToolType,
            baby_id: Optional[int]
    ) -> Dict[str, Any]:
        """Enhanced parameter extraction using Claude"""

        parameter_extraction_prompt = f"""Extract parameters from this user query for a {tool_type.value} tool:

QUERY: "{query}"
TOOL TYPE: {tool_type.value}

Extract relevant parameters like:
- Time ranges (today, this week, last 7 days, specific dates, etc.)
- Limits (number of results, top N, recent X, etc.)
- Filters (specific activities, caregivers, types, etc.)
- Sorting preferences (recent first, oldest first, by duration, etc.)
- Analysis depth (summary, detailed, with trends, etc.)

Provide response as JSON:
{{
    "timeframe": "integer of detected time range by days or null",
    "include_details": "true or false to include details",
}}"""

        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=1000,
                temperature=0.1,
                messages=[{"role": "user", "content": parameter_extraction_prompt}]
            )

            response_content = response.content[0].text if response.content else "{}"

            # Parse JSON response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                parameters = json.loads(json_str)

                # Add baby_id and execution metadata
                parameters["baby_id"] = baby_id
                parameters["extraction_method"] = "claude_ai"
                parameters["extraction_timestamp"] = time.time()

                return parameters

        except Exception as e:
            logger.error(f"Parameter extraction failed: {str(e)}")

        # Enhanced fallback parameters based on tool type
        fallback_params = {
            "baby_id": baby_id,
            "extraction_method": "fallback",
            "extraction_timestamp": time.time()
        }

        # Tool-specific defaults
        if tool_type == ToolType.ACTIVITY_ANALYZER:
            fallback_params.update({
                "limit": 20,
                "time_range": "today",
                "sort_order": "recent_first"
            })
        elif tool_type == ToolType.SLEEP_PATTERN_ANALYZER:
            fallback_params.update({
                "timeframe": 7,
                "include_details": True
            })
        elif tool_type == ToolType.CARE_METRICS_ANALYZER:
            fallback_params.update({
                "time_range": "today",
                "analysis_depth": "summary"
            })
        else:
            fallback_params.update({
                "limit": 10,
                "time_range": "recent"
            })

        return fallback_params

    def _fallback_tool_selection(self, query: str, available_tools: List[Type[Tool]]) -> list[Type[Tool]]:
        """Enhanced fallback tool selection using keyword matching"""
        selected_tools = []
        query_lower = query.lower()

        # Enhanced keyword-based tool selection
        tool_keywords = {
            ToolType.ACTIVITY_ANALYZER: [
                'activity', 'activities', 'recent', 'what did', 'what happened',
                'today', 'summary', 'daily', 'routine', 'schedule', 'events'
            ],
            ToolType.SLEEP_PATTERN_ANALYZER: [
                'sleep', 'sleeping', 'nap', 'rest', 'bedtime', 'night',
                'tired', 'wake', 'dream', 'slumber'
            ],
            ToolType.FEEDING_TRACKER: [
                'feed', 'feeding', 'eat', 'eating', 'meal', 'food',
                'nutrition', 'bottle', 'breast', 'formula'
            ],
            ToolType.HEALTH_MONITOR: [
                'health', 'sick', 'fever', 'temperature', 'symptom',
                'doctor', 'medical', 'medication', 'wellness'
            ],
            ToolType.GROWTH_TRACKER: [
                'growth', 'growing', 'weight', 'height', 'size',
                'development', 'bigger', 'heavier', 'taller'
            ],
            ToolType.MILESTONE_TRACKER: [
                'milestone', 'achievement', 'development', 'progress',
                'learning', 'skill', 'ability', 'new'
            ],
            ToolType.CARE_METRICS_ANALYZER: [
                'care', 'caregiver', 'who', 'participation', 'sharing',
                'helped', 'taking care', 'babysitter', 'parent'
            ],
            ToolType.SCHEDULE_ASSISTANT: [
                'schedule', 'upcoming', 'events', 'appointments', 'when',
                'next', 'calendar', 'plan', 'reminder'
            ]
        }

        # Score tools based on keyword matches
        tool_scores = {}
        for tool in available_tools:
            tool_type_keywords = tool_keywords.get(tool.tool_type, [])
            score = sum(1 for keyword in tool_type_keywords if keyword in query_lower)
            if score > 0:
                tool_scores[tool] = score

        # Select tools with highest scores
        if tool_scores:
            sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
            # Take top tools up to max limit
            selected_tools = [tool for tool, score in sorted_tools[:self.config.max_tools_per_query]]

        # Default to activity analyzer if no specific match
        if not selected_tools and available_tools:
            activity_tool = next(
                (t for t in available_tools if t.tool_type == ToolType.ACTIVITY_ANALYZER),
                available_tools[0]
            )
            selected_tools.append(activity_tool)

        return selected_tools

    async def format_tool_results_for_claude(
            self,
            tool_results: List[Dict[str, Any]],
            original_query: str,
            selection_reasoning: str
    ) -> Dict[str, Any]:
        """Enhanced result formatting with structured data"""

        return {
            "query_context": {
                "original_query": original_query,
                "selection_reasoning": selection_reasoning,
                "processing_timestamp": datetime.utcnow().isoformat(),
                "result_count": len(tool_results)
            },
            "results": tool_results,
            "summary": {
                "total_tools_executed": len(tool_results),
                "successful_results": len([r for r in tool_results if r.get("status") != "error"]),
                "has_errors": any(r.get("status") == "error" for r in tool_results),
                "data_points": sum(
                    len(r.get("data", [])) if isinstance(r.get("data"), list) else 1
                    for r in tool_results if r.get("status") != "error"
                )
            },
            "metadata": {
                "api_version": "v2.0",
                "processing_method": "claude_ai_enhanced",
                "schema_version": "2025.1"
            }
        }