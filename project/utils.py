import os
import time
import subprocess
import re
import hashlib
from urllib.parse import urlparse, urlunparse

# Function to check if the file exists
def wait_for_file(file_path, timeout=60, check_interval=1):
    start_time = time.time()
    while not os.path.exists(file_path):
        elapsed_time = time.time() - start_time
        if elapsed_time >= timeout:
            print(f"Timeout reached: File '{file_path}' not found.")
            return False
        time.sleep(check_interval)
    print(f"File '{file_path}' exists.")
    return True

# Function to validate the platform URL
def check_social_url(url):
    patterns = {
        "Instagram": r"(https?://)?(www\.)?instagram\.com/.*",
        "YouTube": r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.*",
        "TikTok": r"(https?://)?(www\.)?tiktok\.com/.*"
    }
    for platform, pattern in patterns.items():
        if re.match(pattern, url):
            return platform
    return "Unknown"

# Function to generate a media ID using the URL
def generate_media_id(url):
    parsed_url = urlparse(url)
    normalized_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, parsed_url.query, parsed_url.fragment))
    
    hash_func = hashlib.md5()  
    hash_func.update(normalized_url.encode('utf-8'))
    media_id = hash_func.hexdigest()  # Use the complete hash value
    return media_id
