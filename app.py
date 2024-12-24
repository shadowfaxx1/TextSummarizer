import time
from flask import Flask, request, jsonify
import os
import uuid
import re
import instaloader
from TikTokApi import TikTokApi
import subprocess
from flask import send_file,Response

import requests

# Initialize Flask app
app = Flask(__name__)

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
        
        # Check if the duration exceeds 5 minutes (300 seconds)
        if duration > 300:
            # Generate a temporary file path for the trimmed output
            file_dir, file_name = os.path.split(file_path)
            file_base, file_ext = os.path.splitext(file_name)
            temp_file = os.path.join(file_dir, f"{file_base}_trimmed{file_ext}")

            
            # Trim the media file to 5 minutes using ffmpeg
            print("Trimming the media file to 5 minutes...")
            process= subprocess.run(
                [
                    "ffmpeg", "-y", "-i", file_path, "-t", "300", "-c", "copy", temp_file
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

def download_media(url,media_id,platform_type, media_type="video", download_path="downloads"):
 
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    try:
        # Download from YouTube
        if platform_type == "YouTube":
            try:
                # Set the output template

                # Construct the youtube-dl command
                if media_type == "video":
                 output_template = os.path.join(download_path, f"{media_id}.mp4")
                 command = [
                    "yt-dlp",
                    "--no-playlist",
                    "--format", "mp4",
                    "-o", output_template,
                    url
                ]
                elif media_type == "audio":
                    output_template = os.path.join(download_path, f"{media_id}.mp3")
                    command = [
                        "yt-dlp",
                        "--no-playlist",
                        "--extract-audio",
                        "--audio-format", "mp3",
                        "-o", output_template,
                     url
                 ]
                else:
                    return "Invalid media type. Choose 'video' or 'audio'."

                # Execute the command
                subprocess.run(command, check=True)
                wait_for_file(output_template, timeout=60)
                return output_template

            except subprocess.CalledProcessError as e:
                return f"Error downloading YouTube {media_type}: {e}"

        # Download from Instagram
        elif platform_type == "Instagram":
            loader = instaloader.Instaloader()
            post = instaloader.Post.from_shortcode(loader.context, url.split("/")[-2]).video_url
            video_path = os.path.join(download_path, f"{media_id}.mp4")
            response = requests.get(post, stream=True)
            if response.status_code == 200:
                with open(video_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        file.write(chunk)
            else:
                print(f"Failed to download video. HTTP Status Code: {response.status_code}")
            wait_for_file(video_path, timeout=60)
            if media_type == "video":
                return video_path
            elif media_type == "audio":
                audio_path = os.path.join(download_path,  f"{media_id}.mp3")
                convert_to_mp3(video_path, audio_path)
                os.remove(video_path)
                return audio_path

        # Download from TikTok
        elif platform_type == "TikTok":
            api = TikTokApi()
            video = api.video(url=url)
            video_data = video.bytes()
            video_filename = os.path.join(download_path,  f"{media_id}.mp4")
            with open(video_filename, "wb") as f:
                f.write(video_data)
                
            wait_for_file(video_filename, timeout=60)
            if media_type == "video":
                return video_filename
            elif media_type == "audio":
                audio_filename = os.path.join(download_path,  f"{media_id}.mp3")
                convert_to_mp3(video_filename, audio_filename)
                os.remove(video_filename)
                return audio_filename

        else:
            return "Unsupported platform. Please provide a URL from YouTube, Instagram, or TikTok."

    except Exception as e:
        return f"Error occurred: {e}"
 

#streamable video 
@app.route('/downloads/<filename>', methods=['GET'])  #curl -i -H "Range: bytes=0-1024" http://127.0.0.1:5000/downloads/<filename>
def serve_media(filename):
    file_path = os.path.join("downloads")
    

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    range_header = request.headers.get("Range", None)
    if not range_header:
        return send_file(file_path+f"/{filename}.mp4", as_attachment=False)
    try:
        range_match = re.search(r"(\d+)-(\d*)", range_header)
        if not range_match:
            return jsonify({"error": "Invalid Range header"}), 400

        start, end = range_match.groups()
        start = int(start)
        file_size = os.path.getsize(file_path+f"/{filename}.mp4")
        end = int(end) if end else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            return jsonify({"error": "Invalid Range"}), 416

        with open(file_path+f"/{filename}.mp4", "rb") as f:
            f.seek(start)
            chunk = f.read(end - start + 1)  


        response = Response(chunk, 206, mimetype="video/mp4")
        response.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
        return response
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# ________


@app.route('/Audios',methods=["POST"])
def audio_extractor():
    try: 
        url = request.json['url']
    except:
        return jsonify({"error": "Not POST"}), 400
    media_url = 

        

    

@app.route("/upload", methods=["POST"])
def upload_media():
    data = request.json
    media_url = data.get("url")
    media_type = data.get("type")  # "video" or "audio"
    media_id = str(uuid.uuid4())
    
    if not media_url or not media_type:
        return jsonify({"error": "URL and type are required"}), 400
    platform_type = check_social_url(media_url)
    if platform_type == "Unknown":
        return jsonify({"error": "Unsupported platform. Please provide a URL from YouTube, Instagram, or TikTok."}), 400
    
    # Download the media
    path = download_media(media_url, media_id, platform_type, media_type)
    path = trim_media_file(path)
    
    return jsonify({"message": "Media uploaded successfully", "url": f"http://127.0.0.1:5000/downloads/{media_id}", "id": media_id , "path" :f"{os.path.abspath(os.getcwd())}\\{path}"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)