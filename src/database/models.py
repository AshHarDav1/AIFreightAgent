"""Database models"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Load(Base):
    """Freight load model"""
    __tablename__ = 'loads'
    
    id = Column(Integer, primary_key=True)
    load_id = Column(String, unique=True, nullable=False, index=True)  # DAT load ID
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    miles = Column(Integer)
    rate = Column(Float)
    equipment_type = Column(String)
    pickup_date = Column(DateTime)
    delivery_date = Column(DateTime)
    weight = Column(Float)
    commodity = Column(String)
    broker_name = Column(String)
    broker_email = Column(String)
    broker_phone = Column(String)
    dat_url = Column(String)
    raw_data = Column(Text)  # Store raw scraped data as JSON
    status = Column(String, default='new')  # new, contacted, responded, booked, expired
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="load")
    
    def __repr__(self):
        return f"<Load(id={self.id}, load_id='{self.load_id}', {self.origin} -> {self.destination})>"


class Broker(Base):
    """Broker model"""
    __tablename__ = 'brokers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String)
    company = Column(String)
    response_rate = Column(Float, default=0.0)  # Percentage of responses
    last_contacted = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="broker")
    
    def __repr__(self):
        return f"<Broker(id={self.id}, name='{self.name}', email='{self.email}')>"


class Message(Base):
    """Message model - tracks messages sent to brokers"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    load_id = Column(Integer, ForeignKey('loads.id'), nullable=False)
    broker_id = Column(Integer, ForeignKey('brokers.id'), nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='sent')  # sent, delivered, opened, replied, bounced
    response_received = Column(Boolean, default=False)
    response_text = Column(Text)
    response_received_at = Column(DateTime)
    
    # Relationships
    load = relationship("Load", back_populates="messages")
    broker = relationship("Broker", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, load_id={self.load_id}, broker_id={self.broker_id}, status='{self.status}')>"


class ScrapeLog(Base):
    """Log of scraping activities"""
    __tablename__ = 'scrape_logs'
    
    id = Column(Integer, primary_key=True)
    scrape_date = Column(DateTime, default=datetime.utcnow)
    loads_found = Column(Integer, default=0)
    loads_new = Column(Integer, default=0)
    loads_updated = Column(Integer, default=0)
    status = Column(String, default='success')  # success, error, partial
    error_message = Column(Text)
    duration_seconds = Column(Float)
    
    def __repr__(self):
        return f"<ScrapeLog(id={self.id}, date={self.scrape_date}, loads_found={self.loads_found})>"
