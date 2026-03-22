from sqlalchemy.orm import Session
from ..models.image import ImageRecord
from datetime import datetime

def create_image_record(db: Session, original_filename: str, original_path: str):
    db_image = ImageRecord(
        original_filename=original_filename,
        original_path=original_path,
        created_at=datetime.utcnow()
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image

def update_processed(db: Session, image_id: int, filter_name: str, params: dict, result_path: str):
    image = db.query(ImageRecord).filter(ImageRecord.id == image_id).first()
    if image:
        image.filter_applied = filter_name
        image.params = str(params)
        image.result_path = result_path
        image.processed_at = datetime.utcnow()
        db.commit()
        db.refresh(image)
    return image