from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn
from typhoon_ocr import ocr_document
import tempfile
import shutil
import logging
import time
from datetime import datetime
import cv2
import numpy as np
from pdf2image import convert_from_path
from unstructured.partition.auto import partition
from unstructured.elements.models import Element
from text_cleanup import clean_text_pipeline

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Typhoon OCR API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def deskew_image(image: np.ndarray) -> np.ndarray:
    """Corrects skew in an image using the minimum area rectangle method."""
    # Convert to grayscale if it's a color image
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # Invert the image and apply Otsu's threshold to get a binary image of the text
    _, binary_image = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find the coordinates of all white pixels (the text)
    coords = np.column_stack(np.where(binary_image > 0))

    # Get the angle from the minimum area rectangle that encloses the text
    angle = cv2.minAreaRect(coords)[-1]

    # The `cv2.minAreaRect` function returns angles in the range [-90, 0).
    # We need to correct this angle for the rotation.
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    logger.info(f"Detected skew angle: {angle:.2f} degrees")

    # Don't rotate for very small angles to avoid unnecessary processing
    if abs(angle) < 0.1:
        logger.info("Skew angle is negligible, skipping rotation.")
        return image

    # Rotate the image to correct for the skew
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    # Use a white background for filling empty space, which is better for OCR
    rotated_image = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))

    return rotated_image

async def preprocess_and_save(file_path: str, original_filename: str, page_num: int) -> str:
    """
    Preprocesses a file by converting it to a high-quality image, deskewing it,
    and saving it to a new temporary file. Returns the path to the processed file.
    """
    processed_file_path = None
    try:
        file_ext = os.path.splitext(original_filename)[1].lower()

        if file_ext == ".pdf":
            logger.info(f"Converting PDF page {page_num} to image.")
            # Use a high DPI for better quality OCR results
            images = convert_from_path(file_path, first_page=page_num, last_page=page_num, dpi=300)
            if not images:
                raise HTTPException(status_code=400, detail=f"Could not extract page {page_num} from PDF.")
            # Convert PIL image (from pdf2image) to OpenCV format (numpy array)
            image = np.array(images[0])
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            logger.info("Reading image file.")
            image = cv2.imread(file_path)
            if image is None:
                raise HTTPException(status_code=400, detail="Could not read the uploaded image file.")

        logger.info("Starting image pre-processing (deskewing).")
        deskewed_image_np = deskew_image(image)

        # Save the processed image to a new temporary file in a lossless format
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_proc_file:
            is_success, buffer = cv2.imencode(".png", deskewed_image_np)
            if not is_success:
                raise Exception("Failed to encode processed image.")
            temp_proc_file.write(buffer)
            processed_file_path = temp_proc_file.name

        logger.info(f"Saved pre-processed file to: {processed_file_path}")
        return processed_file_path

    except Exception as e:
        if processed_file_path and os.path.exists(processed_file_path):
            os.unlink(processed_file_path)
        logger.error(f"Error during pre-processing: {str(e)}")
        raise e

@app.post("/process")
async def process_document(
    file: UploadFile = File(...),
    page_num: int = Form(1),
    task_type: str = Form("default"),
    use_unstructured: bool = Form(False),
    perform_cleanup: bool = Form(True)
):
    start_time = time.time()
    logger.info(f"Request for {file.filename} (Page: {page_num}, Unstructured: {use_unstructured}, Cleanup: {perform_cleanup})")
    
    temp_file_path = None
    processed_file_path = None
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        logger.info(f"Saved temporary copy of original file to: {temp_file_path}")

        processed_file_path = await preprocess_and_save(temp_file_path, file.filename, page_num)

        if use_unstructured:
            logger.info(f"Starting layout analysis with Unstructured on {processed_file_path}")
            elements = partition(filename=processed_file_path, strategy="hi_res")
            result = [el.to_dict() for el in elements]
            if perform_cleanup:
                logger.info("Performing cleanup on Unstructured output.")
                for item in result:
                    item['text'] = clean_text_pipeline(item.get('text', ''))
        else:
            logger.info(f"Starting standard OCR on {processed_file_path}")
            result = ocr_document(
                pdf_or_image_path=processed_file_path,
                task_type=task_type,
                page_num=1
            )
            if perform_cleanup:
                logger.info("Performing cleanup on standard OCR output.")
                result = clean_text_pipeline(result)

        end_time = time.time()
        processing_time = end_time - start_time
        minutes = int(processing_time // 60)
        seconds = int(processing_time % 60)
        
        logger.info(f"Processing finished successfully. Time taken: {minutes}m {seconds}s")
        
        return {
            "result": result,
            "processing_time": {
                "minutes": minutes,
                "seconds": seconds,
                "total_seconds": processing_time
            }
        }
    except Exception as e:
        logger.error(f"An error occurred in the main processing endpoint: {str(e)}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.info(f"Deleted original temp file: {temp_file_path}")
        if processed_file_path and os.path.exists(processed_file_path):
            os.unlink(processed_file_path)
            logger.info(f"Deleted processed temp file: {processed_file_path}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    host = os.getenv("TYPHOON_OCR_HOST", "0.0.0.0")
    port = int(os.getenv("TYPHOON_OCR_PORT", "8000"))
    logger.info(f"เริ่มต้น server ที่ {host}:{port}")
    uvicorn.run(app, host=host, port=port) 