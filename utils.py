import re
import os

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def ensure_folder(path):
    os.makedirs(path, exist_ok=True)
