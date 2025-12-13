# server/rag/ocr_adapter.py

import logging
from typing import Optional
from io import BytesIO

from .slide_models import SlideData, MIN_NATIVE_TEXT_CHARS, LARGE_IMAGE_RATIO

logger = logging.getLogger(__name__)


# Wrapper for Tesseract OCR
# Handles missing dependencies gracefully
class OCRAdapter:
    def __init__(self):
        try:
            import pytesseract
            from PIL import Image
            self.pytesseract = pytesseract
            self.Image = Image
            self.available = True
            logger.info("Tesseract OCR adapter initialized")
        except ImportError:
            self.available = False
            logger.warning("pytesseract or Pillow not available - OCR disabled")
    
    # Extracts text from image bytes using Tesseract
    # Returns empty string if OCR unavailable or fails
    def extract_text(self, image_bytes: bytes) -> str:
        if not self.available:
            return ""
        
        try:
            # 1. Open image from bytes
            image = self.Image.open(BytesIO(image_bytes))
            # 2. Run OCR
            text = self.pytesseract.image_to_string(image)
            return text
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return ""


# Factory function to get OCR adapter
# Returns None if OCR unavailable
def get_ocr_adapter() -> Optional[OCRAdapter]:
    adapter = OCRAdapter()
    if adapter.available:
        return adapter
    
    logger.warning("OCR not available - slide ingestion will work but image text may be missing")
    return None


# Checks if a slide needs OCR based on text/image ratios
# Returns True if OCR should be applied
def should_ocr_slide(slide: SlideData) -> bool:
    # 1. Calculate total native text length
    native_text_len = sum(len(block.text) for block in slide.text_blocks)
    num_images = len(slide.image_blocks)
    
    # 2. Check if large image dominates slide
    slide_area = slide.width * slide.height
    largest_image_ratio = 0.0
    for img_block in slide.image_blocks:
        img_area = img_block.bbox[2] * img_block.bbox[3]
        if slide_area > 0:
            ratio = img_area / slide_area
            largest_image_ratio = max(largest_image_ratio, ratio)
    
    # 3. OCR if low text + images, or large image
    if native_text_len < MIN_NATIVE_TEXT_CHARS and num_images > 0:
        return True
    
    if largest_image_ratio > LARGE_IMAGE_RATIO:
        return True
    
    return False