"""Language choices supported by the reused component SDKs."""
LANGUAGES = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
             "fr": "French", "de": "German", "es": "Spanish", "ar": "Arabic", "th": "Thai"}
SOURCE_LANGUAGES = ("zh", "en")


def target_for(source, target=None):
    if source not in SOURCE_LANGUAGES:
        raise ValueError("Source language must be Chinese or English")
    if target is None:
        return "en" if source == "zh" else "zh"
    if not isinstance(target, str) or target not in LANGUAGES:
        raise ValueError("Unsupported translation target language")
    if source == target:
        raise ValueError("Source and target languages must differ")
    return target
