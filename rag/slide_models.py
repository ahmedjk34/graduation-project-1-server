from typing import List, Optional

#python-pptx gives you the dimensions of the slide in EMUs (English Metric Units)
#PyMuPDF gives you the dimensions of the slide in points

# TextBlock: Represents a text block on a slide
# ImageBlock: Represents an image block on a slide
# SlideData: Represents a complete slide with all extracted content

# What am I trying to do:
# I want to create a model that represents a slide with all the extracted content
# The tool allows us to read the slides on a fundamental level, and we use tricks that I learnt from my Image Processing course
# Which is, identify objects [in this case, blocks of text and images] as boxes, then I can deal with each slide depending on it's content easily
# My idea is to use the Image OCR properly, I don't want it to process the Najah logo that is on slides for example, or some random blocks that aren't intended to be images but they are due to weird PDF parsing
# So, the first step is to identify the blocks of text and images on the slide, and then we can process it properly

# Represents a text block on a slide
class TextBlock:
    def __init__(self, text: str, bbox: List[float], font_size: Optional[float] = None):
        self.text = text #the actual content
        self.bbox = bbox #the bounding box of the text block
        self.font_size = font_size #the font size of the text block [can be used later to estimate the importance of the text block, get an approximate idea of the importance of the text block, and text in it]


# Represents an image block on a slide
class ImageBlock:
    def __init__(self, image_bytes: Optional[bytes] = None, bbox: List[float] = None):
        self.image_bytes = image_bytes #the actual image bytes
        self.bbox = bbox if bbox else [0, 0, 0, 0] #the bounding box of the image block


# Represents a complete slide with all extracted content
class SlideData:
    def __init__(self, deck_id: str, slide_number: int, width: float, height: float,
                 text_blocks: List[TextBlock] = None, image_blocks: List[ImageBlock] = None,
                 notes_text: Optional[str] = None, ocr_text_blocks: List[TextBlock] = None):
        self.deck_id = deck_id #the id of the deck [we will save this into supabase for identifying the deck]
        self.slide_number = slide_number 
        self.width = width
        self.height = height
        self.text_blocks = text_blocks if text_blocks else []
        self.image_blocks = image_blocks if image_blocks else []
        self.notes_text = notes_text #this is specific for pptx slides, it contains the notes text of the slide
        self.ocr_text_blocks = ocr_text_blocks if ocr_text_blocks else []


# OCR decision constants

# Minimum native text characters to skip OCR
# If slide has < 50 chars of native text + has images, run OCR on images to extract embedded text
MIN_NATIVE_TEXT_CHARS = 50
LARGE_IMAGE_RATIO = 0.40 #the maximum ratio of the area of an image block to the area of the slide to be considered for OCR

