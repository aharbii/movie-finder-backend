from pydantic import BaseModel

class FeedbackCreate(BaseModel):
    message_id: int
    movie_title: str
    is_positive: bool

class FeedbackResponse(FeedbackCreate):
    id: int

    class Config:
        from_attributes = True
