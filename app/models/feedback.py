from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from app.core.database import Base

class Feedback(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message_id = Column(Integer, ForeignKey("messages.id"))
    movie_title = Column(String)
    is_positive = Column(Boolean)
