"""Conservative application terminology, preserving the original ASR/display text."""
import re

def translation_input(text, language):
    if language != 'en':
        return text
    # Only noun/file contexts identify the technical filename. Ordinary requests
    # such as "Can you read me a story?" must retain their original meaning.
    text = re.sub(r'\b((?:a|an|the|your|our|this|that|whole|entire|long|short)\s+)read\s+me\b',
                  lambda m: m[1]+'README', text, flags=re.I)
    return re.sub(r'\bread\s+me(?=\s+(?:file|document)\b|\.md\b)', 'README', text, flags=re.I)
