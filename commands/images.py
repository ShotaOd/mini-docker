import json
import os
import subprocess

from dataclasses import dataclass
from terminaltables import AsciiTable

import commands.config as config

from typing import List


@dataclass
class Image:
    name: str
    version: str
    size: int
    cmd: List[str]
    dir: str

    @property
    def content_dir(self):
        return os.path.join(self.dir, 'contents')

def find_images() -> List[Image]:
    images = []
    for image_dir_name in os.listdir(config.IMAGE_DIR):
        image_dir = os.path.join(config.IMAGE_DIR, image_dir_name)
        with open(os.path.join(image_dir, 'manifest.json'), 'r') as manifest_file:
            manifest = json.loads(manifest_file.read())

        layers_path = os.path.join(image_dir, 'layers')

        size = sum(
            os.path.getsize(os.path.join(layers_path, layer))
            for layer in os.listdir(layers_path) if os.path.isfile(os.path.join(layers_path, layer))
        )

        # デフォルトのコマンドを取得する
        state = json.loads(manifest['history'][0]['v1Compatibility'])
        cmd = state['config']['Cmd']
        # print(json.dumps(manifest, indent=2))

        image = Image(manifest['name'], manifest['tag'], size, cmd, image_dir)
        images.append(image)

    return images


def run_images():
    images = find_images()
    header = [['name', 'version', 'size', 'path']]
    data = header + [[img.name, img.version, sizeof_fmt(img.size), img.dir] for img in images]
    table = AsciiTable(data)
    print(table.table)


def sizeof_fmt(num, suffix='B'):
    # http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)
