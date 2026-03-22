from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])

@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(req: FeedbackCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fb = Feedback(
        user_id=current_user.id,
        message_id=req.message_id,
        movie_title=req.movie_title,
        is_positive=req.is_positive
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return fb
