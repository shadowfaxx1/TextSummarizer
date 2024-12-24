from flask import Flask, request, jsonify, send_file, Response
from media import download_media, trim_media_file
from utils import generate_media_id, check_social_url
import os
import re
app = Flask(__name__)

@app.route("/upload", methods=["POST"])
def upload_media():
    data = request.json
    media_url = data.get("url")
    media_type = data.get("type")  # "video" or "audio"
    if not media_url or not media_type:
        return jsonify({"error": "URL and type are required"}), 400

    platform_type = check_social_url(media_url)
    if platform_type == "Unknown":
        return jsonify({"error": "Unsupported platform. Please provide a URL from YouTube, Instagram, or TikTok."}), 400
    
    media_id = generate_media_id(media_url)
    
    # Download the media
    media_path = download_media(media_url, media_id, platform_type, media_type)
    media_path = trim_media_file(media_path)
    
    return jsonify({"message": "Media uploaded successfully", "url": f"http://127.0.0.1:5000/downloads/{media_id}", "id": media_id})

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
