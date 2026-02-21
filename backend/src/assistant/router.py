import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.config import settings
from src.common.database import get_db
from src.assistant.models import AssistantConversation
from src.assistant.schemas import ChatMessage, ConversationResponse, ConversationSummary
from src.assistant.tools import TOOL_DEFINITIONS, execute_tool

router = APIRouter(prefix="/assistant", tags=["assistant"])

SYSTEM_PROMPT = """You are the internal operations assistant for EVA (goeva.ai), an AI SaaS company \
run by Jose Pedro Gama and Gustavo Cermeno. You have access to financial data, \
customer records, tasks, prospects, meetings, OKRs, service costs (never secrets), \
and KPIs. Answer concisely. Use tables for lists. Show currency as original + USD when relevant. \
Today's date context will be included. Always use the available tools to answer data questions \
instead of guessing."""


@router.post("/chat")
async def chat(
    body: ChatMessage,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    import openai
    from datetime import date

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    # Get or create conversation
    if body.conversation_id:
        result = await db.execute(
            select(AssistantConversation)
            .where(AssistantConversation.id == body.conversation_id, AssistantConversation.user_id == user.id)
        )
        convo = result.scalar_one_or_none()
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        convo = AssistantConversation(user_id=user.id, title=None, messages_json=[])
        db.add(convo)
        await db.flush()
        await db.refresh(convo)

    # Add user message
    messages_list = list(convo.messages_json or [])
    messages_list.append({"role": "user", "content": body.message})

    # Auto-title from first message
    if not convo.title and len(messages_list) == 1:
        convo.title = body.message[:100]

    # Build context for LLM — last 20 messages
    context_messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\nToday is {date.today().isoformat()}."}
    ]
    context_messages.extend(messages_list[-20:])

    # Run tool loop (non-streaming first pass)
    max_tool_rounds = 5
    for _ in range(max_tool_rounds):
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=context_messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            # Add assistant message with tool calls
            context_messages.append(msg.model_dump())

            for tc in msg.tool_calls:
                tool_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tool_result = await execute_tool(tc.function.name, tool_args, db)
                context_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            # Final text response
            assistant_content = msg.content or ""
            messages_list.append({"role": "assistant", "content": assistant_content})
            convo.messages_json = messages_list
            db.add(convo)
            await db.commit()

            async def generate():
                yield f"data: {json.dumps({'conversation_id': str(convo.id), 'delta': assistant_content})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

    # Fallback if tool loop exceeded
    messages_list.append({"role": "assistant", "content": "I'm having trouble processing that request. Please try again."})
    convo.messages_json = messages_list
    db.add(convo)
    await db.commit()

    async def fallback():
        yield f"data: {json.dumps({'conversation_id': str(convo.id), 'delta': 'I had trouble processing that. Please try again.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(fallback(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AssistantConversation)
        .where(AssistantConversation.user_id == user.id)
        .order_by(AssistantConversation.updated_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    convo = AssistantConversation(user_id=user.id, title=None, messages_json=[])
    db.add(convo)
    await db.flush()
    await db.refresh(convo)
    return convo


@router.get("/conversations/{convo_id}", response_model=ConversationResponse)
async def get_conversation(
    convo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AssistantConversation)
        .where(AssistantConversation.id == convo_id, AssistantConversation.user_id == user.id)
    )
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.delete("/conversations/{convo_id}", status_code=204)
async def delete_conversation(
    convo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AssistantConversation)
        .where(AssistantConversation.id == convo_id, AssistantConversation.user_id == user.id)
    )
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(convo)
    await db.commit()
