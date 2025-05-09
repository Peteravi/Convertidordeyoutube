import os
import re
import uuid
import logging
import subprocess
from flask import Flask, request, jsonify, send_file, after_this_request, send_from_directory
import yt_dlp as youtube_dl
from pytube import YouTube

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración Flask
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['UPLOAD_FOLDER'] = 'temp_files'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB
app.config['COOKIES_FILE'] = 'cookies.txt'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def sanitize_filename(filename):
    keepchars = (' ', '.', '_', '-')
    return "".join(c for c in filename if c.isalnum() or c in keepchars).rstrip()

def convert_to_mp3(input_path):
    output_path = input_path.rsplit('.', 1)[0] + ".mp3"
    subprocess.run([
        'ffmpeg', '-y', '-i', input_path,
        '-vn', '-ab', '192k', '-ar', '44100', '-f', 'mp3', output_path
    ], check=True)
    os.remove(input_path)
    return output_path

def download_with_ytdlp(url, output_format):
    try:
        video_id = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url).group(1)
        clean_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]',
            'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(title)s.%(ext)s'),
            'quiet': False,
            'noplaylist': True,
            'retries': 5,
            'fragment_retries': 5,
            'concurrent_fragment_downloads': 5,
            'cookiefile': app.config['COOKIES_FILE'] if os.path.exists(app.config['COOKIES_FILE']) else None,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0',
                'Accept-Language': 'es-ES,es;q=0.9',
            }
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            original_filename = ydl.prepare_filename(info)

            base_name = sanitize_filename(info.get('title', 'video'))[:50]
            unique_id = str(uuid.uuid4())[:8]
            output_filename = f"{base_name}_{unique_id}.{output_format}"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

            if output_format == 'mp3':
                mp3_path = convert_to_mp3(original_filename)
                os.rename(mp3_path, output_path)
            else:
                if not original_filename.endswith('.mp4'):
                    new_path = original_filename.rsplit('.', 1)[0] + '.mp4'
                    os.rename(original_filename, new_path)
                    original_filename = new_path
                os.rename(original_filename, output_path)

            return output_path, output_filename, None

    except Exception as e:
        raise Exception(f"YT-DLP Error: {str(e)}")

def download_with_pytube(url, output_format):
    try:
        yt = YouTube(url)
        base_name = sanitize_filename(yt.title)[:50]
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"{base_name}_{unique_id}.{output_format}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        if output_format == 'mp3':
            stream = yt.streams.filter(only_audio=True).first()
            temp_file = output_path.replace('.mp3', '.mp4')
            stream.download(filename=temp_file)
            final_path = convert_to_mp3(temp_file)
            os.rename(final_path, output_path)
        else:
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            stream.download(filename=output_path)

        return output_path, output_filename, None

    except Exception as e:
        raise Exception(f"Pytube Error: {str(e)}")

def download_video(url, output_format):
    try:
        logger.info(f"Intentando descargar: {url}")
        try:
            return download_with_ytdlp(url, output_format)
        except Exception as yt_err:
            logger.warning(f"yt-dlp falló: {str(yt_err)}. Intentando con pytube...")
            return download_with_pytube(url, output_format)
    except Exception as e:
        logger.error(f"Error en download_video: {str(e)}", exc_info=True)
        return None, None, str(e)

@app.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.get_json()
        url = data.get('url')
        output_format = data.get('format', 'mp3').lower()

        if not url:
            return jsonify({'error': 'URL requerida'}), 400
        if output_format not in ['mp3', 'mp4']:
            return jsonify({'error': 'Formato no válido'}), 400

        file_path, output_filename, error = download_video(url, output_format)

        if error:
            return jsonify({
                'error': error,
                'solutions': [
                    'Actualiza cookies.txt si es necesario',
                    'Prueba con otro video',
                    'Verifica tu conexión o vuelve a intentarlo'
                ]
            }), 500

        @after_this_request
        def cleanup(response):
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error limpiando archivo: {str(e)}")
            return response

        return send_file(
            file_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='audio/mpeg' if output_format == 'mp3' else 'video/mp4'
        )

    except Exception as e:
        logger.error(f"Error en /convert: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/')
def home():
    return send_from_directory('templates', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
