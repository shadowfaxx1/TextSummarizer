import os
import subprocess
from config import DOWNLOAD_PATH, MAX_DURATION, SUPPORTED_MEDIA_EXTENSIONS
import requests
import instaloader
from TikTokApi import TikTokApi
from utils import wait_for_file

import yt_dlp

# Function to trim the media file to a maximum duration (5 minutes)
def trim_media_file(file_path):
    print(f"Checking the duration of the media file: {file_path}...")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist or is not a valid file.")
    try:
        # Get the media file duration using ffprobe
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "format=duration", "-of", "csv=p=0", file_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode != 0:
            print(f"Error with ffprobe: {result.stderr}")
            raise RuntimeError("ffprobe failed.")
        
        duration = float(result.stdout.strip())
        
        # Check if the duration exceeds the max allowed time
        if duration > MAX_DURATION:
            # Trim the media file to 5 minutes using ffmpeg
            file_dir, file_name = os.path.split(file_path)
            file_base, file_ext = os.path.splitext(file_name)
            temp_file = os.path.join(file_dir, f"{file_base}_trimmed{file_ext}")
            print("Trimming the media file to 5 minutes...")
            process = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", file_path, "-t", str(MAX_DURATION), "-c", "copy", temp_file
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if process.returncode != 0:
                print(f"Error with ffmpeg: {process.stderr}")
                raise RuntimeError("ffmpeg trimming failed.")
            # Overwrite the original file
            os.replace(temp_file, file_path)
        
        return file_path
    
    except Exception as e:
        raise RuntimeError(f"An error occurred while processing the media file: {e}")

# Function to download media based on platform type (YouTube, Instagram, TikTok)
def download_media(url, media_id, platform_type, media_type="video"):
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    try:
        if platform_type == "YouTube":
            return download_from_youtube(url, media_id, media_type)
        elif platform_type == "Instagram":
            return download_from_instagram(url, media_id, media_type)
        elif platform_type == "TikTok":
            return download_from_tiktok(url, media_id, media_type)
        else:
            return "Unsupported platform."

    except Exception as e:
        return f"Error occurred: {e}"

# Download from YouTube using yt-dlp
def download_from_youtube(url, media_id, media_type):
    output_template = os.path.join(DOWNLOAD_PATH, f"{media_id}.mp4" if media_type == "video" else f"{media_id}.mp3")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--format", "mp4" if media_type == "video" else "bestaudio",
        "-o", output_template,
        url
    ]
    subprocess.run(command, check=True)
    wait_for_file(output_template)
    return output_template

# Download from Instagram using Instaloader
def download_from_instagram(url, media_id, media_type):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',  # Download best video and audio
        'outtmpl': os.path.join(DOWNLOAD_PATH, f'{media_id}.mp4'),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        video_path = os.path.join(DOWNLOAD_PATH, f"{media_id}.mp4")
        wait_for_file(video_path)
        return video_path
    except Exception as e:
        raise RuntimeError(f"Error downloading from Instagram: {e}")

# Download from TikTok using TikTokApi
def download_from_tiktok(url, media_id, media_type):
    api = TikTokApi()
    video = api.video(url=url)
    video_data = video.bytes()
    video_filename = os.path.join(DOWNLOAD_PATH, f"{media_id}.mp4")
    with open(video_filename, "wb") as f:
        f.write(video_data)
    wait_for_file(video_filename)
    if media_type == "audio":
        audio_filename = os.path.join(DOWNLOAD_PATH, f"{media_id}.mp3")
        convert_to_mp3(video_filename, audio_filename)
        os.remove(video_filename)
        return audio_filename
    return video_filename

# Function to convert video to audio (MP3)
def get_audio_stream_count(input_file):
    result = subprocess.run(
        ["ffprobe", "-i", input_file, "-show_streams", "-select_streams", "a", "-loglevel", "error"],
        stdout=subprocess.PIPE,
        text=True,
        check=False
    )
    if result.returncode != 0:
            print(f"Error with ffprobe: {result.stderr}")
            raise RuntimeError("ffprobe failed.")
    return result.stdout.count("index")

def convert_to_mp3(input_file, output_file):
    audio_streams = get_audio_stream_count(input_file)
    if audio_streams > 0:
        command = [
            "ffmpeg",
            "-i", input_file,
            "-filter_complex", f"[0:a]amerge=inputs={audio_streams}",
            "-ac", "2",
            output_file
        ]
        process=subprocess.run(command)
        if process.returncode != 0:
            print(f"Error with ffmpeg: {process.stderr}")
            raise RuntimeError("ffmpeg trimming failed.")
        print(f"Converted to {output_file} with {audio_streams} merged streams.")
    else:
        print("No audio streams found in the input file.")