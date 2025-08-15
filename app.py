import os
import json
import re
import yt_dlp
from flask import Flask, request, jsonify, render_template, send_from_directory, Response

# --- App Initialization ---
# The 'template_folder' is set to 'templates' to match our new folder structure.
app = Flask(__name__, template_folder='templates')

# --- Constants ---
DOWNLOAD_FOLDER = 'downloads'
HISTORY_FILE = 'download_history.json'

# --- Initial Setup ---
# Create the download folder if it doesn't exist
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- Helper Functions ---
def get_download_history():
    """Reads the download history from a JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_download_history(history):
    """Saves the download history to a JSON file."""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)

# --- App Routes ---
@app.route('/')
def index():
    """Renders the main HTML page from the 'templates' folder."""
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    """
    Fetches detailed video information including title, thumbnail, and available resolutions.
    """
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        ydl_opts = {'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get all unique video resolutions available
            resolutions = set()
            for f in info.get('formats', []):
                if f.get('height'):
                    resolutions.add(f['height'])

            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                # Send a sorted list of resolutions
                'resolutions': sorted(list(resolutions), reverse=True)
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_video', methods=['POST'])
def download_video():
    """
    Downloads a video by selecting the best video and audio for the chosen resolution
    and merging them together.
    """
    url = request.json.get('url')
    resolution = request.json.get('resolution')
    title = request.json.get('title')
    thumbnail = request.json.get('thumbnail')

    if not all([url, resolution, title, thumbnail]):
        return jsonify({'error': 'URL, resolution, title, and thumbnail are required'}), 400

    try:
        # Define a clean output filename template
        output_template = os.path.join(DOWNLOAD_FOLDER, '%(title)s [%(id)s].%(ext)s')
        
        # This format string tells yt-dlp to find the best video at the chosen
        # resolution (or lower) and the best audio, and merge them.
        # It defaults to mp4 format.
        format_selector = f"bestvideo[height<={resolution}]+bestaudio/best[ext=mp4]/best"
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': output_template,
            'merge_output_format': 'mp4', # Ensures the final file is mp4
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Get the final filename after download and potential merge
            filename = ydl.prepare_filename(info)

            # Add to history with more details
            history = get_download_history()
            history.insert(0, {
                'title': title, 
                'filename': os.path.basename(filename),
                'thumbnail': thumbnail
            })
            save_download_history(history)

            return jsonify({'message': 'Download complete!', 'filename': os.path.basename(filename)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def history():
    """Returns the download history."""
    return jsonify(get_download_history())

@app.route('/play/<path:filename>')
def play_file(filename):
    """Streams a downloaded video file for playback in the browser."""
    video_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(video_path):
        return "File not found", 404
    
    range_header = request.headers.get('Range', None)
    size = os.path.getsize(video_path)
    
    if not range_header:
        # If no range header, send the whole file
        with open(video_path, 'rb') as f:
            data = f.read()
        return Response(data, mimetype='video/mp4', headers={'Content-Length': str(size)})

    # Handle byte range requests for seeking
    byte1, byte2 = 0, None
    m = re.search(r'(\d+)-(\d*)', range_header)
    g = m.groups()

    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1])

    length = size - byte1
    if byte2 is not None:
        length = byte2 - byte1 + 1
    
    data = None
    with open(video_path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)

    rv = Response(data, 206, mimetype='video/mp4', content_type='video/mp4', direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{size}')
    return rv


if __name__ == '__main__':
    app.run(debug=True)
