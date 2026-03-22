from .base import Base, engine
from ..models.image import ImageRecord   # import all models

# Create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)