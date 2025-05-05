import inspect
import json
import logging
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware  # Add CORS middleware
from langchain_core._api import LangChainBetaWarning
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel
from langgraph.types import Command, Interrupt

from agents import DEFAULT_AGENT, get_agent, get_all_agent_info
from core import settings
from memory import initialize_database
from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    FeedbackResponse,
    ServiceMetadata,
    StreamInput,
    UserInput,
)
from service.utils import (
    convert_message_content_to_string,
    langchain_to_chat_message,
    remove_tool_calls,
)

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
logger = logging.getLogger(__name__)


def verify_bearer(
    http_auth: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(description="Bearer authentication with API key.", auto_error=False)),
    ],
) -> None:
    """
    Verify the Bearer token against the configured AUTH_SECRET.
    
    If AUTH_SECRET is not set, authentication is bypassed (development mode only).
    In production, AUTH_SECRET should always be set.
    """
    if not settings.AUTH_SECRET:
        logger.warning("AUTH_SECRET is not set - API endpoints are unprotected!")
        return
        
    auth_secret = settings.AUTH_SECRET.get_secret_value()
    if not http_auth or http_auth.credentials != auth_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Configurable lifespan that initializes the appropriate database checkpointer based on settings.
    """
    try:
        async with initialize_database() as saver:
            await saver.setup()
            agents = get_all_agent_info()
            for a in agents:
                agent = get_agent(a.key)
                agent.checkpointer = saver
            yield
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        raise


app = FastAPI(lifespan=lifespan)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development (adjust for production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

router = APIRouter(dependencies=[Depends(verify_bearer)])


@router.get("/info")
async def info() -> ServiceMetadata:
    return ServiceMetadata(
        agents=get_all_agent_info(),
        default_agent=DEFAULT_AGENT,
    )


async def _handle_input(user_input: UserInput, agent: Pregel) -> tuple[dict[str, Any], UUID]:
    """
    Parse user input and handle any required interrupt resumption.
    Returns kwargs for agent invocation and the run_id.
    """
    run_id = uuid4()
    thread_id = user_input.thread_id or str(uuid4())
    user_id = user_input.user_id

    # Build configurable dictionary
    configurable = {
        "thread_id": thread_id
    }
    
    # Add model if provided
    if user_input.model:
        configurable["model"] = user_input.model
    
    # Add user_id to the configurable if provided
    if user_id:
        configurable["user_id"] = user_id

    # Add agent_config
    if user_input.agent_config:
        if overlap := configurable.keys() & user_input.agent_config.keys():
            raise HTTPException(
                status_code=422,
                detail=f"agent_config contains reserved keys: {overlap}",
            )
        configurable.update(user_input.agent_config)

    # Get Langfuse callback handler
    from core.telemetry import get_langfuse_callback
    langfuse_handler = get_langfuse_callback(user_id=user_id, session_id=thread_id)
    
    # Build RunnableConfig
    config_kwargs = {
        "configurable": configurable,
        "run_id": run_id,
    }
    
    # Add callbacks if available
    if langfuse_handler:
        config_kwargs["callbacks"] = [langfuse_handler]
        
    config = RunnableConfig(**config_kwargs)

    # Check for interrupts that need to be resumed
    state = await agent.aget_state(config=config)
    interrupted_tasks = [
        task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
    ]

    # Prepare input
    if interrupted_tasks:
        # assume user input is response to resume agent execution from interrupt
        input = Command(resume=user_input.message)
    else:
        input = {"messages": [HumanMessage(content=user_input.message)]}

    kwargs = {
        "input": input,
        "config": config,
    }

    return kwargs, run_id


@router.post("/{agent_id}/invoke")
@router.post("/invoke")
async def invoke(user_input: UserInput, agent_id: str = DEFAULT_AGENT) -> ChatMessage:
    """
    Invoke an agent with user input to retrieve a final response.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to messages for recording feedback.
    """
    # NOTE: Currently this only returns the last message or interrupt.
    # In the case of an agent outputting multiple AIMessages (such as the background step
    # in interrupt-agent, or a tool step in research-assistant), it's omitted. Arguably,
    # you'd want to include it. You could update the API to return a list of ChatMessages
    # in that case.
    agent: Pregel = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent)
    try:
        response_events: list[tuple[str, Any]] = await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore # fmt: skip
        response_type, response = response_events[-1]
        if response_type == "values":
            # Normal response, the agent completed successfully
            output = langchain_to_chat_message(response["messages"][-1])
        elif response_type == "updates" and "__interrupt__" in response:
            # The last thing to occur was an interrupt
            # Return the value of the first interrupt as an AIMessage
            output = langchain_to_chat_message(
                AIMessage(content=response["__interrupt__"][0].value)
            )
        else:
            raise ValueError(f"Unexpected response type: {response_type}")

        output.run_id = str(run_id)
        return output
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


async def message_generator(
    user_input: StreamInput, agent_id: str = DEFAULT_AGENT
) -> AsyncGenerator[str, None]:
    """
    Generate a stream of messages from the agent.

    This is the workhorse method for the /stream endpoint.
    """
    agent: Pregel = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent)

    try:
        # Process streamed events from the graph and yield messages over the SSE stream.
        async for stream_event in agent.astream(
            **kwargs, stream_mode=["updates", "messages", "custom"]
        ):
            if not isinstance(stream_event, tuple):
                continue
            stream_mode, event = stream_event
            new_messages = []
            if stream_mode == "updates":
                # Send node updates to the client
                if user_input.stream_node_updates is not False:  # Default to True if not specified
                    for node, updates in event.items():
                        # Include the actual update values in a safe way
                        try:
                            # If updates is too large or complex, we'll include a simplified version
                            update_info = {
                                "node": node,
                                "has_updates": updates is not None and len(updates) > 0,
                                "updates": _simplify_node_updates(updates),
                                "run_id": str(run_id)  # Include the run_id in node updates
                            }
                            yield f"data: {json.dumps({'type': 'node_update', 'content': update_info})}\n\n"
                        except Exception as e:
                            logger.warning(f"Error while serializing node update: {e}")
                            # Fallback to basic info if serialization fails
                            update_info = {
                                "node": node,
                                "has_updates": updates is not None and len(updates) > 0,
                                "error": "Could not serialize node updates",
                                "run_id": str(run_id)  # Include the run_id in fallback info too
                            }
                            yield f"data: {json.dumps({'type': 'node_update', 'content': update_info})}\n\n"
                
                for node, updates in event.items():
                    # A simple approach to handle agent interrupts.
                    # In a more sophisticated implementation, we could add
                    # some structured ChatMessage type to return the interrupt value.
                    if node == "__interrupt__":
                        interrupt: Interrupt
                        for interrupt in updates:
                             new_messages.append(AIMessage(content=interrupt.value))
                        continue
                    updates = updates or {}
                    update_messages = updates.get("messages", [])
                    # special cases for using langgraph-supervisor library
                    if node == "supervisor":
                        # Get only the last AIMessage since supervisor includes all previous messages
                        ai_messages = [msg for msg in update_messages if isinstance(msg, AIMessage)]
                        if ai_messages:
                            update_messages = [ai_messages[-1]]
                    if node in ("research_expert", "math_expert"):
                        # By default the sub-agent output is returned as an AIMessage.
                        # Convert it to a ToolMessage so it displays in the UI as a tool response.
                        msg = ToolMessage(
                            content=update_messages[0].content,
                            name=node,
                            tool_call_id="",
                        )
                        update_messages = [msg]
                    new_messages.extend(update_messages)

            if stream_mode == "custom":
                new_messages = [event]

            # LangGraph streaming may emit tuples: (field_name, field_value)
            # e.g. ('content', <str>), ('tool_calls', [ToolCall,...]), ('additional_kwargs', {...}), etc.
            # We accumulate only supported fields into `parts` and skip unsupported metadata.
            # More info at: https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages/
            processed_messages = []
            current_message: dict[str, Any] = {}
            for message in new_messages:
                if isinstance(message, tuple):
                    key, value = message
                    # Store parts in temporary dict
                    current_message[key] = value
                else:
                    # Add complete message if we have one in progress
                    if current_message:
                        processed_messages.append(_create_ai_message(current_message))
                        current_message = {}
                    processed_messages.append(message)

            # Add any remaining message parts
            if current_message:
                processed_messages.append(_create_ai_message(current_message))

            for message in processed_messages:
                try:
                    chat_message = langchain_to_chat_message(message)
                    chat_message.run_id = str(run_id)
                except Exception as e:
                    logger.error(f"Error parsing message: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                    continue
                # LangGraph re-sends the input message, which feels weird, so drop it
                if chat_message.type == "human" and chat_message.content == user_input.message:
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

            if stream_mode == "messages":
                if not user_input.stream_tokens:
                    continue
                msg, metadata = event
                if "skip_stream" in metadata.get("tags", []):
                    continue
                # For some reason, astream("messages") causes non-LLM nodes to send extra messages.
                # Drop them.
                if not isinstance(msg, AIMessageChunk):
                    continue
                content = remove_tool_calls(msg.content)
                if content:
                    # Empty content in the context of OpenAI usually means
                    # that the model is asking for a tool to be invoked.
                    # So we only print non-empty content.
                    yield f"data: {json.dumps({'type': 'token', 'content': convert_message_content_to_string(content)})}\n\n"
    except Exception as e:
        logger.error(f"Error in message generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


def _create_ai_message(parts: dict) -> AIMessage:
    sig = inspect.signature(AIMessage)
    valid_keys = set(sig.parameters)
    filtered = {k: v for k, v in parts.items() if k in valid_keys}
    return AIMessage(**filtered)


def _simplify_node_updates(updates: Any) -> dict[str, Any]:
    """
    Process node updates to create a simplified, serializable representation.
    This extracts useful information from complex node update objects.
    """
    if updates is None:
        return {}
    
    # Handle dictionaries directly
    if isinstance(updates, dict):
        result = {}
        # Extract and process messages if present
        if "messages" in updates:
            try:
                result["messages"] = [
                    {
                        "type": _get_message_type(msg),
                        "content": _get_message_content(msg),
                    }
                    for msg in updates.get("messages", [])
                ]
            except Exception:
                # If extraction fails, just indicate messages are present
                result["messages"] = "[Messages present but could not be serialized]"
        
        # Add other keys from the updates dict
        for key, value in updates.items():
            if key != "messages":  # Skip messages as we've already processed them
                try:
                    # Try to serialize the value, if it fails, store a placeholder
                    json.dumps(value)  # Test if serializable
                    result[key] = value
                except (TypeError, OverflowError):
                    # If value isn't JSON serializable, store a simpler representation
                    result[key] = f"[Complex data: {type(value).__name__}]"
        
        return result
    
    # For non-dict objects, provide a basic representation
    try:
        # Try direct serialization first
        json.dumps(updates)
        return {"value": updates}
    except (TypeError, OverflowError):
        # If that fails, return a simpler representation
        return {"value": f"[Complex data: {type(updates).__name__}]"}


def _get_message_type(message: Any) -> str:
    """Get the type of a message object."""
    if hasattr(message, "__class__"):
        class_name = message.__class__.__name__
        if "HumanMessage" in class_name:
            return "human"
        elif "AIMessage" in class_name:
            return "ai"
        elif "ToolMessage" in class_name or "FunctionMessage" in class_name:
            return "tool"
        else:
            return class_name
    return "unknown"


def _get_message_content(message: Any) -> str:
    """Safely extract content from a message object."""
    if hasattr(message, "content"):
        content = message.content
        # Convert content to string if it's not already
        if not isinstance(content, str):
            try:
                if isinstance(content, list):
                    # Handle list of content parts (common in OpenAI responses)
                    parts = []
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            parts.append(part["text"])
                        elif isinstance(part, str):
                            parts.append(part)
                    return " ".join(parts)
                else:
                    return str(content)
            except Exception:
                return "[Complex content]"
        return content
    return "[No content]"


def _sse_response_example() -> dict[int | str, Any]:
    return {
        status.HTTP_200_OK: {
            "description": "Server Sent Event Response",
            "content": {
                "text/event-stream": {
                    "example": "data: {'type': 'token', 'content': 'Hello'}\n\ndata: {'type': 'token', 'content': ' World'}\n\ndata: [DONE]\n\n",
                    "schema": {"type": "string"},
                }
            },
        }
    }


@router.post(
    "/{agent_id}/stream",
    response_class=StreamingResponse,
    responses=_sse_response_example(),
)
@router.post("/stream", response_class=StreamingResponse, responses=_sse_response_example())
async def stream(user_input: StreamInput, agent_id: str = DEFAULT_AGENT) -> StreamingResponse:
    """
    Stream an agent's response to a user input, including intermediate messages and tokens.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to all messages for recording feedback.

    Set `stream_tokens=false` to return intermediate messages but not token-by-token.
    """
    return StreamingResponse(
        message_generator(user_input, agent_id),
        media_type="text/event-stream",
    )


@router.post("/feedback")
async def feedback(feedback: Feedback) -> FeedbackResponse:
    """
    Record feedback for a run using Langfuse.

    This is a simple wrapper for the Langfuse score API, so the
    credentials can be stored and managed in the service rather than the client.
    """
    try:
        # Get Langfuse credentials from settings or environment variables
        from langfuse import Langfuse
        import os
        from core import settings
        from pydantic import SecretStr
        
        # Get credentials directly from environment or settings
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY") or getattr(settings, "LANGFUSE_PUBLIC_KEY", None)
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY") or getattr(settings, "LANGFUSE_SECRET_KEY", None)
        host = os.environ.get("LANGFUSE_HOST") or getattr(settings, "LANGFUSE_HOST", None) or "https://cloud.langfuse.com"
        
        # Check if credentials are available
        if not public_key or not secret_key:
            logger.error("Langfuse credentials not found, cannot record feedback")
            raise HTTPException(status_code=500, detail="Langfuse credentials not found")
        
        # Handle SecretStr type
        if isinstance(public_key, SecretStr):
            public_key = public_key.get_secret_value()
        if isinstance(secret_key, SecretStr):
            secret_key = secret_key.get_secret_value()
        
        # Create Langfuse client with explicit credentials
        langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
        
        # Log for debugging
        logger.info(f"Submitting feedback for run_id: {feedback.run_id}")
        
        # Convert feedback to Langfuse score
        langfuse.score(
            id=str(uuid4()),  # Generate a unique ID
            trace_id=feedback.run_id,  # Use run_id as trace_id
            name=feedback.key,  # Use the feedback key as the score name
            value=feedback.score,  # Use the feedback score as the value
            comment=feedback.kwargs.get("comment", "") if feedback.kwargs else "",
        )
        
        return FeedbackResponse()
    except Exception as e:
        logger.error(f"Error recording feedback with Langfuse: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error recording feedback: {str(e)}")


@router.post("/history")
def history(input: ChatHistoryInput) -> ChatHistory:
    """
    Get chat history.
    """
    # TODO: Hard-coding DEFAULT_AGENT here is wonky
    agent: Pregel = get_agent(DEFAULT_AGENT)
    try:
        state_snapshot = agent.get_state(
            config=RunnableConfig(
                configurable={
                    "thread_id": input.thread_id,
                }
            )
        )
        messages: list[AnyMessage] = state_snapshot.values["messages"]
        chat_messages: list[ChatMessage] = [langchain_to_chat_message(m) for m in messages]
        return ChatHistory(messages=chat_messages)
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(router)
