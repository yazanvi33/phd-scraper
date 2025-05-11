import logging
from flask import Flask, render_template, request, jsonify
import yt_dlp
import json
import re
import os

# إعداد logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# إعداد المجلدات
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_PATH, 'exports')
SINGLE_VIDEOS_DIR = os.path.join(EXPORTS_DIR, 'single_videos')
PLAYLISTS_DIR = os.path.join(EXPORTS_DIR, 'playlists')
for directory in [EXPORTS_DIR, SINGLE_VIDEOS_DIR, PLAYLISTS_DIR]:
    os.makedirs(directory, exist_ok=True)

def sanitize_filename(filename):
    """ تنظيف اسم الملف من الأحرف غير المسموح بها في أنظمة الملفات """
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def format_index(index, total_videos):
    """ تنسيق رقم الفيديو ليحتوي على أصفار بادئة بناءً على عدد الفيديوهات """
    digits = len(str(total_videos))
    return f"{index:0{digits}d}"

def get_video_info(video_url):
    """ جلب معلومات فيديو واحد باستخدام yt-dlp """
    ydl_opts = {
        'quiet': True,
        'simulate': True,
        'skip_download': True,
        'get_description': True,
    }

    try:
        logger.debug(f"Attempting to fetch video info for URL: {video_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_data = {
                'index': '',  # سيتم تعبئته لاحقًا في قوائم التشغيل
                'id': info.get('id', ''),
                'title': info.get('title', ''),
                'uploader': info.get('uploader', ''),
                'upload_date': info.get('upload_date', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'like_count': info.get('like_count', 0),
                'view_count': info.get('view_count', 0),
                'tags': info.get('tags', []),
                'categories': info.get('categories', []),
                'cast': info.get('cast', []),
                'description': info.get('description', '')
            }
            logger.debug(f"Successfully fetched video info for URL: {video_url}")
            return video_data
    except Exception as e:
        logger.error(f"Error fetching video info for URL {video_url}: {str(e)}")
        return None

def get_playlist_info(playlist_url, start_index=None, end_index=None, selected_indices=None):
    """ جلب معلومات الفيديوهات في قائمة تشغيل مع عرض التقدم """
    ydl_opts = {
        'quiet': True,
        'simulate': True,
        'skip_download': True,
        'extract_flat': True,
    }

    try:
        logger.debug(f"Attempting to fetch playlist info for URL: {playlist_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            videos = playlist_info.get('entries', [])
            total_videos = len(videos)

            if total_videos == 0:
                logger.warning(f"No videos found in playlist: {playlist_url}")
                yield {'status': 'error', 'message': 'No videos found in the playlist.'}
                return

            # تحديد الفهارس بناءً على المدخلات
            if selected_indices:
                indices = [int(idx) for idx in selected_indices]
                range_total = len(indices)
            else:
                if start_index is None or end_index is None:
                    start_index = 1
                    end_index = total_videos
                else:
                    start_index = max(1, start_index)
                    end_index = min(total_videos, end_index)
                indices = list(range(start_index, end_index + 1))
                range_total = len(indices)

            video_data_list = []
            for i, index in enumerate(indices, 1):
                video = videos[index - 1]
                video_url = video.get('url')
                video_data = get_video_info(video_url)
                if video_data:
                    video_data['index'] = format_index(index, total_videos)
                    video_data_list.append(video_data)
                    formatted_index = format_index(index, total_videos)
                    yield {'status': 'progress', 'message': f"Retrieved video {formatted_index}/{total_videos}", 'current': i, 'total': range_total}
            yield {'status': 'complete', 'video_data_list': video_data_list}
    except Exception as e:
        logger.error(f"Error fetching playlist info for URL {playlist_url}: {str(e)}")
        yield {'status': 'error', 'message': f'Failed to retrieve playlist information: {str(e)}'}

def list_playlist_videos(playlist_url):
    """ جلب قائمة بأسماء الفيديوهات في قائمة التشغيل """
    ydl_opts = {
        'quiet': True,
        'simulate': True,
        'skip_download': True,
        'extract_flat': True,
    }

    try:
        logger.debug(f"Attempting to list videos for playlist URL: {playlist_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            videos = playlist_info.get('entries', [])
            total_videos = len(videos)
            video_list = [
                {
                    'index': format_index(i + 1, total_videos),
                    'title': video.get('title', 'Unknown Title')
                }
                for i, video in enumerate(videos)
            ]
            logger.debug(f"Successfully listed {total_videos} videos for playlist URL: {playlist_url}")
            return total_videos, video_list
    except Exception as e:
        logger.error(f"Error listing videos for playlist URL {playlist_url}: {str(e)}")
        return 0, []

def save_to_json(data, filename, directory):
    """ حفظ البيانات في ملف JSON ضمن المجلد المحدد """
    if not data:
        logger.warning("No data provided to save to JSON")
        return False
    filepath = os.path.join(directory, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.debug(f"Successfully saved data to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {str(e)}")
        return False

@app.route('/')
def index():
    """ عرض الواجهة الرئيسية """
    logger.debug("Rendering index page")
    return render_template('index.html')

@app.route('/fetch_videos', methods=['POST'])
def fetch_videos():
    """ معالجة طلب جلب المعلومات باستخدام الـ streaming لجميع الحالات """
    logger.debug("Received request to fetch videos")
    try:
        data = request.get_json()
        if not data:
            logger.error("No data provided in request")
            return jsonify({'status': 'error', 'message': 'No data provided in request.'}), 400

        logger.debug(f"Request data: {data}")
        input_type = data.get('input_type', '').lower()
        url = data.get('url')
        playlist_name = sanitize_filename(data.get('playlist_name', 'playlist'))
        range_type = data.get('range_type')
        start_index = data.get('start_index')
        end_index = data.get('end_index')
        selected_indices = data.get('selected_indices')

        if not url:
            logger.error("No URL provided in request")
            return jsonify({'status': 'error', 'message': 'No URL provided.'}), 400

        logger.debug(f"Processing {input_type} request for URL: {url}")
        def generate():
            if input_type == 'video':
                video_data = get_video_info(url)
                if video_data:
                    filename = f"{sanitize_filename(video_data['title'])}_info.json"
                    if save_to_json([video_data], filename, SINGLE_VIDEOS_DIR):
                        logger.info(f"Video information saved to {os.path.join(SINGLE_VIDEOS_DIR, filename)}")
                        yield json.dumps({'status': 'success', 'message': f'Video information saved to {filename}'}) + '\n'
                    else:
                        yield json.dumps({'status': 'error', 'message': 'Failed to save video information.'}) + '\n'
                else:
                    yield json.dumps({'status': 'error', 'message': 'Failed to retrieve video information.'}) + '\n'
            elif input_type == 'playlist':
                # معالجة حالات قائمة التشغيل
                if range_type == 'entire':
                    # جلب كامل القائمة
                    logger.debug("Fetching entire playlist")
                    generator = get_playlist_info(url)
                else:
                    # Specific Range: تحديد النطاق أو الـ checkboxes
                    use_range = False
                    start_idx = None
                    end_idx = None
                    try:
                        if start_index and end_index:  # إذا كانت الحقول غير فارغة
                            start_idx = int(start_index)
                            end_idx = int(end_index)
                            use_range = True
                            logger.debug(f"Using range: {start_idx}-{end_idx}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid range provided: {str(e)}")
                        yield json.dumps({'status': 'error', 'message': 'Invalid range provided.'}) + '\n'
                        return

                    if use_range:
                        # استخدام النطاق المحدد
                        generator = get_playlist_info(url, start_index=start_idx, end_index=end_idx)
                    else:
                        # استخدام الـ checkboxes إذا كانت موجودة
                        if selected_indices and len(selected_indices) > 0:
                            logger.debug(f"Using selected indices: {selected_indices}")
                            generator = get_playlist_info(url, selected_indices=selected_indices)
                        else:
                            # إذا لم يتم تحديد شيء، أبلغ المستخدم
                            logger.error("No range or checkboxes selected")
                            yield json.dumps({'status': 'error', 'message': 'Please specify a range or select videos using checkboxes.'}) + '\n'
                            return

                progress_messages = []
                for item in generator:
                    if item['status'] == 'progress':
                        progress_messages.append(item['message'])
                        yield json.dumps(item) + '\n'
                    elif item['status'] == 'complete':
                        video_data_list = item['video_data_list']
                        if video_data_list:
                            filename = f"{playlist_name}_{len(video_data_list)}.json"
                            if save_to_json(video_data_list, filename, PLAYLISTS_DIR):
                                yield json.dumps({'status': 'success', 'message': f'Playlist information saved to {filename}'}) + '\n'
                            else:
                                yield json.dumps({'status': 'error', 'message': 'Failed to save playlist information.'}) + '\n'
                        else:
                            yield json.dumps({'status': 'error', 'message': 'No videos were retrieved from the playlist.'}) + '\n'
                    elif item['status'] == 'error':
                        yield json.dumps(item) + '\n'
                        break
            else:
                logger.error(f"Invalid input type: {input_type}")
                yield json.dumps({'status': 'error', 'message': 'Invalid input type.'}) + '\n'

        return app.response_class(generate(), mimetype='application/json')

    except Exception as e:
        logger.error(f"Unexpected error in fetch_videos: {str(e)}")
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/list_playlist_videos', methods=['POST'])
def list_playlist_videos_route():
    """ جلب قائمة الفيديوهات لعرضها في الجدول """
    logger.debug("Received request to list playlist videos")
    try:
        url = request.json.get('url')
        if not url:
            logger.error("No URL provided in request")
            return jsonify({'status': 'error', 'message': 'No URL provided.'}), 400

        total_videos, video_list = list_playlist_videos(url)
        if total_videos == 0:
            logger.error("Failed to retrieve playlist information")
            return jsonify({'status': 'error', 'message': 'Failed to retrieve playlist information.'}), 400

        logger.info(f"Successfully retrieved {total_videos} videos for playlist")
        return jsonify({
            'status': 'success',
            'total_videos': total_videos,
            'videos': video_list
        })
    except Exception as e:
        logger.error(f"Unexpected error in list_playlist_videos_route: {str(e)}")
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application")
    app.run(debug=True)