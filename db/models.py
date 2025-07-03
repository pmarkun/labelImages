from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
import datetime

Base = declarative_base()

class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    date = Column(Date)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    participants = relationship("Participant", back_populates="race", cascade="all, delete-orphan")

class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    data = Column(Text)  # JSON string

    race = relationship("Race", back_populates="participants")
