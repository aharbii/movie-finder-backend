from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.chat import Conversation, Message
from app.schemas.chat import ConversationResponse, ChatRequest, MessageResponse
from app.services.agent import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .options(selectinload(Conversation.messages))
    )
    return result.scalars().all()

@router.post("/", response_model=MessageResponse)
async def chat_with_agent(req: ChatRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if req.conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == req.conversation_id, Conversation.user_id == current_user.id))
        conv = result.scalars().first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(user_id=current_user.id, title=req.message[:50])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
    
    # Save user message
    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)
    await db.commit()
    
    # Run Agent Context
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.asc())
    )
    history = result.scalars().all()
    
    # Invoke LangChain Agent
    agent_response_content = await run_agent(history, req.message)
    
    # Save AI Response
    ai_msg = Message(conversation_id=conv.id, role="ai", content=agent_response_content)
    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)
    
    return ai_msg
