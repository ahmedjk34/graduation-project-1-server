import re
from typing import List, Set

# The goal of this file is to normalize the text of the slides, and the text of the images
# We want to make sure that the text is consistent, and the images are consistent
# My first thought was using an LLM to do this, but I think it's better to use smart heuristics and rules to do this
# You can think of this file as "Text hygiene before intelligence."

# Normalizes bullet characters to consistent format
# Converts various bullet types to "- "
def normalize_bullet_characters(text: str) -> str:
    bullet_patterns = [
        r'^[\u2022\u2023\u25E6\u2043\u2219\u00B7]\s*',
        r'^[–—]\s*',
        r'^[-]\s*',
        r'^[*]\s*',
    ]
    
    lines = text.split('\n')
    normalized_lines = []
    
    # 1. Replace each bullet pattern with "- "
    for line in lines:
        normalized_line = line
        for pattern in bullet_patterns:
            normalized_line = re.sub(pattern, '- ', normalized_line)
        normalized_lines.append(normalized_line)
    
    return '\n'.join(normalized_lines)


# Finds lines that repeat across most slides (headers/footers)
# Returns set of repeated lines to filter out
# all_text_blocks: is a list of lists of text blocks, each list is a slide
# repetition_threshold: is the threshold for the number of slides that a line must appear in to be considered repeated
def remove_repeated_headers_footers(all_text_blocks: List[List], repetition_threshold: float = 0.65) -> Set[str]:
    if not all_text_blocks:
        return set()
    
    # 1. Count line occurrences across all slides
    line_counts = {}
    total_slides = len(all_text_blocks)

    # 2. Calculate the minimum number of slides that a line must appear in to be considered repeated
    min_slides = int(total_slides * repetition_threshold)
    
    for slide_blocks in all_text_blocks:
        seen_in_slide = set()
        for block in slide_blocks:
            text = block.get("text") if isinstance(block, dict) else block.text
            lines = text.split('\n')
            
            # 2. Normalize and count each line
            # We need to normalize the lines to make sure that the lines are consistent
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                line_normalized = re.sub(r'\s+', ' ', line_stripped.lower())
                if line_normalized not in seen_in_slide:
                    line_counts[line_normalized] = line_counts.get(line_normalized, 0) + 1
                    seen_in_slide.add(line_normalized)
    
    # 3. Find lines that appear in too many slides
    repeated_lines = {line for line, count in line_counts.items() if count >= min_slides}
    return repeated_lines


# Cleans up OCR text by removing noise
# Keeps meaningful words and acronyms
# Sometimes OCR can mess up, from testing, this was one OCR block for example:
"""
| | |
A
---
///
ACTUAL TEXT WAS HERE


/--// 
a
a

[MORE NOISE ...]
"""

def denoise_ocr_text(text: str) -> str:
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # 1. Skip empty lines
        if not line_stripped:
            continue
        
        # 2. Skip lines that are only punctuation
        if re.match(r'^[^\w\s]+$', line_stripped):
            continue
        
        # 3. Filter words - keep long words or acronyms [removes individual characters]
        words = line_stripped.split()
        filtered_words = []
        for word in words:
            if len(word) >= 3 or re.match(r'^[A-Z0-9]+$', word):
                filtered_words.append(word)
        
        if filtered_words:
            cleaned_lines.append(' '.join(filtered_words))
    
    return '\n'.join(cleaned_lines)


# Applies all normalization steps to slide text
# Normalizes bullets and removes repeated headers/footers
def normalize_slide_text(text: str, repeated_lines: Set[str] = None) -> str:
    if repeated_lines is None:
        repeated_lines = set()
    
    # 1. Normalize bullets
    normalized = normalize_bullet_characters(text)
    
    # 2. Remove repeated headers/footers
    lines = normalized.split('\n')
    filtered_lines = []
    for line in lines:
        line_normalized = re.sub(r'\s+', ' ', line.strip().lower())
        if line_normalized not in repeated_lines:
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines).strip()
