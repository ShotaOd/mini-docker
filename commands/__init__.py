def parse_image_str(image: str) -> (str, str):
    if '/' in image:
        last_idx = image.rfind('/')
        return image[:last_idx], image[last_idx + 1:]
    else:
        return 'library', image
