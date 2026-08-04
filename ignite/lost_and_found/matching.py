"""Small, local image matcher used by the lost-and-found workflow.

The matcher deliberately avoids an external service: uploaded images stay in the
project's media storage.  It combines grayscale hashes, colour distribution, and
low-resolution image structure, returning a repeatable score from 0 to 100.
"""

from collections import Counter

from PIL import Image, ImageOps


MATCH_THRESHOLD = 60


def _prepare(image_field):
    image_field.open("rb")
    try:
        with Image.open(image_field) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            return image.copy()
    finally:
        image_field.close()


def _average_hash(image):
    pixels = list(ImageOps.grayscale(image).resize((8, 8), Image.Resampling.LANCZOS).getdata())
    average = sum(pixels) / len(pixels)
    return tuple(pixel >= average for pixel in pixels)


def _difference_hash(image):
    pixels = list(ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS).getdata())
    return tuple(
        pixels[row * 9 + column] > pixels[row * 9 + column + 1]
        for row in range(8)
        for column in range(8)
    )


def _hash_similarity(first, second):
    return sum(one == two for one, two in zip(first, second)) / len(first)


def _histogram_similarity(first, second):
    def bins(image):
        # Treat a pixel as an RGB colour.  Binning each byte separately makes
        # unrelated solid colours appear overly similar because all contain
        # channel values near zero or 255.
        return Counter(
            tuple(channel // 64 for channel in pixel)
            for pixel in image.resize((48, 48), Image.Resampling.LANCZOS).getdata()
        )

    first_bins, second_bins = bins(first), bins(second)
    overlap = sum(min(first_bins[key], second_bins[key]) for key in first_bins)
    return overlap / max(sum(first_bins.values()), sum(second_bins.values()))


def _structure_similarity(first, second):
    first_pixels = list(ImageOps.grayscale(first).resize((24, 24), Image.Resampling.LANCZOS).getdata())
    second_pixels = list(ImageOps.grayscale(second).resize((24, 24), Image.Resampling.LANCZOS).getdata())
    mean_difference = sum(abs(one - two) for one, two in zip(first_pixels, second_pixels))
    return 1 - (mean_difference / (255 * len(first_pixels)))


def image_similarity(first_photo, second_photo):
    """Return a conservative 0–100 visual similarity score for two image fields."""
    first, second = _prepare(first_photo), _prepare(second_photo)
    score = (
        0.22 * _hash_similarity(_average_hash(first), _average_hash(second))
        + 0.22 * _hash_similarity(_difference_hash(first), _difference_hash(second))
        + 0.41 * _histogram_similarity(first, second)
        + 0.15 * _structure_similarity(first, second)
    )
    return round(max(0, min(1, score)) * 100)


def find_lost_matches(found_photo, lost_items):
    """Return open lost reports whose uploaded photo scores at least 60%."""
    matches = []
    for lost_item in lost_items:
        try:
            score = image_similarity(found_photo, lost_item.photo)
        except (OSError, ValueError):
            # A corrupt legacy image must not prevent other reports from matching.
            continue
        if score >= MATCH_THRESHOLD:
            matches.append((lost_item, score))
    return sorted(matches, key=lambda match: match[1], reverse=True)
