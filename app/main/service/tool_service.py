"""
Tool service for managing tools and their executions.
Handles tool CRUD operations and execution logic.
"""
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Type

from sqlalchemy.orm import Session

from app.main.model.tool import Tool, ToolExecution, ToolType, ToolStatus
from app.main.service.baby_service import _get_baby_ids
from app.main.service.tool.base.registry import ToolRegistry


def create_tool(db: Session, tool_data: Dict[str, Any]) -> Tool:
    """Create a new tool configuration"""
    # Check if tool with same name exists
    existing_tool = db.query(Tool).filter(Tool.name == tool_data['name']).first()
    if existing_tool:
        raise ValueError(f"Tool with name '{tool_data['name']}' already exists")

    # Convert string values to enum instances
    tool_type = ToolType(tool_data['tool_type'])
    status = ToolStatus(tool_data.get('status', ToolStatus.ACTIVE.value))

    new_tool = Tool(
        name=tool_data['name'],
        tool_type=tool_type,
        description=tool_data['description'],
        version=tool_data.get('version', '1.0.0'),
        capabilities=tool_data.get('capabilities', {}),
        configuration=tool_data.get('configuration', {}),
        status=status
    )

    db.add(new_tool)
    db.commit()
    db.refresh(new_tool)
    return new_tool


def get_tool(db: Session, tool_id: int) -> Optional[Tool]:
    """Get a tool by ID"""
    return db.query(Tool).filter(Tool.id == tool_id).first()


def get_tool_by_name(db: Session, name: str) -> Optional[Tool]:
    """Get a tool by name"""
    return db.query(Tool).filter(Tool.name == name).first()


def get_tools_by_type(db: Session, tool_type: ToolType) -> list[Type[Tool]]:
    """Get all tools of a specific type"""
    return db.query(Tool).filter(
        Tool.tool_type == tool_type,
        Tool.status == ToolStatus.ACTIVE
    ).all()


def get_active_tools(db: Session) -> list[Type[Tool]]:
    """Get all active tools"""
    return db.query(Tool).filter(
        Tool.status == ToolStatus.ACTIVE,
        Tool.is_active == True
    ).all()

def get_all_tools(db: Session) -> list[Type[Tool]]:
    """Get all active tools"""
    return db.query(Tool).all()


def update_tool(db: Session, tool_id: int, tool_data: Dict[str, Any]) -> Optional[Tool]:
    """Update a tool configuration"""
    tool = get_tool(db, tool_id)
    if not tool:
        return None

    # Update fields if provided
    if 'tool_type' in tool_data:
        tool.tool_type = ToolType(tool_data['tool_type'])
    if 'name' in tool_data:
        tool.name = tool_data['name']
    if 'description' in tool_data:
        tool.description = tool_data['description']
    if 'version' in tool_data:
        tool.version = tool_data['version']
    if 'capabilities' in tool_data:
        tool.capabilities = tool_data['capabilities']
    if 'configuration' in tool_data:
        tool.configuration = tool_data['configuration']
    if 'status' in tool_data:
        tool.status = ToolStatus(tool_data['status'])

    tool.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(tool)
    return tool


def execute_tool(
        db: Session,
        tool_id: int,
        user_id: int,
        parameters: Dict[str, Any],
        baby_id: Optional[int] = None
) -> Dict[str, Any]:
    """Execute a tool and return the results"""
    # Get baby IDs
    baby_ids = _get_baby_ids(db, user_id, baby_id)

    start_time = time.time()
    execution_id = str(uuid.uuid4())

    # Get the tool
    tool = get_tool(db, tool_id)
    if not tool:
        raise ValueError(f"Tool with ID {tool_id} not found")

    if tool.status != ToolStatus.ACTIVE:
        raise ValueError(f"Tool '{tool.name}' is not active")

    # Create execution record
    execution = ToolExecution(
        execution_id=execution_id,
        tool_id=tool_id,
        user_id=user_id,
        baby_id=baby_id,
        parameters=parameters,
        status="running"
    )
    db.add(execution)
    db.commit()

    try:

        # Use the registry to get executor
        executor_class = ToolRegistry.get_executor(tool.tool_type)
        executor = executor_class(db, tool.configuration)

        # Execute tool
        result = executor.execute(baby_ids, user_id, parameters)

        # Update execution record
        execution_time = int((time.time() - start_time) * 1000)
        execution.result = result
        execution.status = "success"
        execution.execution_time_ms = execution_time

        # Update tool usage stats
        tool.usage_count += 1
        tool.last_used_at = datetime.utcnow()

        db.commit()

        return {
            "tool_id": tool_id,
            "execution_id": execution_id,
            "status": "success",
            "data": result,
            "metadata": {
                "tool_name": tool.name,
                "tool_description": tool.description
            },
            "execution_time_ms": execution_time
        }

    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
        execution.execution_time_ms = int((time.time() - start_time) * 1000)
        db.commit()
        raise