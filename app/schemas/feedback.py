from pydantic import BaseModel, ConfigDict
class FeedbackCreate(BaseModel):
    message_id: int
    movie_title: str
    is_positive: bool

class FeedbackResponse(FeedbackCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
