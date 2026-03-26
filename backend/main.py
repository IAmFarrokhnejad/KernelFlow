from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import numpy as np, cv2, base64, json, asyncio
from pathlib import Path
from app.database.base import engine, get_db, create_tables
from app.models.image import ImageRecord
from app.crud.image import create_image_record, update_processed
from services.filters import process_and_stream, apply_full_filter   # ← added apply_full_filter


app = FastAPI(title="PixelScan Image Filter Studio + DB")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

# Create tables on startup
@app.on_event("startup")
def startup_event():
    create_tables()

@app.post("/api/upload")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    path = UPLOAD_DIR / file.filename
    path.write_bytes(data)
    
    record = create_image_record(db, file.filename, str(path))
    
    return {
        "id": record.id,
        "filename": file.filename,
        "preview": f"/static/{file.filename}"
    }

@app.post("/api/apply/{filter_name}")
async def apply(
    filter_name: str,
    file: UploadFile = File(...),
    params: str = Form("{}"),
    record_id: int = Form(...),
    db: Session = Depends(get_db)
):
    img_bytes = await file.read()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    params_dict = json.loads(params)
    processed = apply_full_filter(img, filter_name, params_dict)   # ← compute full filtered image

    result_filename = f"processed_{record_id}_{filter_name}.jpg"
    result_path = UPLOAD_DIR / result_filename

    async def sse_generator():
        async for frame in process_and_stream(img, filter_name, params_dict):
            if frame == "FINAL_DONE":
                # Save final result to disk + DB (now uses the correctly filtered image)
                cv2.imwrite(str(result_path), processed)
                update_processed(db, record_id, filter_name, params_dict, str(result_path))
                yield "data: FINAL_DONE\n\n"
            else:
                yield f"data: {frame}\n\n"
            await asyncio.sleep(0.01)
    
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

# Optional: Get history
@app.get("/api/history")
def get_history(db: Session = Depends(get_db)):
    return db.query(ImageRecord).all()