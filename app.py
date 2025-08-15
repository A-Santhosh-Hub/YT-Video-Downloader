import os
import sys
import json
import yt_dlp
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

# Create a 'downloads' folder if it doesn't exist
if not os.path.exists('downloads'):
    os.makedirs('downloads')

app = Flask(__name__, static_folder='static', template_folder='templates')

def get_video_info(url):
    """Fetches video information and formats."""
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(url, download=False)
        return meta

@app.route('/')
def index():
    """Serve the main HTML page."""
    return render_template('index.html')

@app.route('/api/get-formats', methods=['POST'])
def get_formats_api():
    """API endpoint to fetch available video formats."""
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        info = get_video_info(url)
        formats = []
        for f in info.get('formats', []):
            # Filter for video formats that have a resolution
            if f.get('vcodec') != 'none' and f.get('height'):
                filesize_mb = f.get('filesize')
                if filesize_mb:
                    filesize_mb = f"{filesize_mb / (1024*1024):.1f} MB"
                else:
                    filesize_mb = "N/A"
                
                formats.append({
                    'format_id': f['format_id'],
                    'resolution': f'{f["height"]}p',
                    'ext': f['ext'],
                    'fps': f.get('fps'),
                    'filesize': filesize_mb,
                })
        
        # Sort by height descending
        formats.sort(key=lambda x: int(x['resolution'][:-1]), reverse=True)

        return jsonify({
            'title': info.get('title', 'No title'),
            'thumbnail': info.get('thumbnail', ''),
            'formats': formats
        })
    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'Invalid URL or video not found: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/api/download')
def download_video_api():
    """API endpoint to download the video and stream progress."""
    url = request.args.get('url')
    format_id = request.args.get('format_id')

    if not url or not format_id:
        return Response(json.dumps({'error': 'URL and Format ID are required'}), status=400, mimetype='application/json')

    def generate_progress():
        """Generator function to stream download progress."""
        def progress_hook(d):
            if d['status'] == 'downloading':
                progress_data = {
                    'status': 'downloading',
                    'percent': d.get('_percent_str', '0%').strip(),
                    'total_bytes': d.get('_total_bytes_str', 'N/A').strip(),
                    'speed': d.get('_speed_str', 'N/A').strip(),
                    'eta': d.get('_eta_str', 'N/A').strip()
                }
                # SSE format: "data: {json_string}\n\n"
                yield f"data: {json.dumps(progress_data)}\n\n"

        ydl_opts = {
            'format': format_id,
            'progress_hooks': [progress_hook],
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'noprogress': True, # Disable default progress bar
            'quiet': True,
            'no_warnings': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Send final status
            finished_data = {'status': 'finished', 'message': '✅ Download complete!'}
            yield f"data: {json.dumps(finished_data)}\n\n"

        except Exception as e:
            error_data = {'status': 'error', 'message': f'❌ Download failed: {str(e)}'}
            yield f"data: {json.dumps(error_data)}\n\n"

    # Use Server-Sent Events (SSE) to stream progress
    return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
