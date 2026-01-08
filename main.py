import os
import csv
import subprocess
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build

# ================= CONFIG =================
CHANNEL_ID = "UCe9xwdRW2D7RYwlp6pRGOvQ"

VIDEOS_CSV = "videos.csv"           # Static metadata
ALL_VIEWS_CSV = "allvideoviews.csv" # Tracks last views and last checked
SUMTOTAL_TXT = "sumtotal.txt"       # Stores cumulative total of new views since tracking began

load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY not found in .env")

youtube = build("youtube", "v3", developerKey=API_KEY)

# ==========================================

def get_uploads_playlist_id():
    """Get the playlist ID for all uploads of the channel"""
    response = youtube.channels().list(
        part="contentDetails",
        id=CHANNEL_ID
    ).execute()
    return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

# ------------------------------------------
def discover_videos():
    """Get all videos for the channel"""
    playlist_id = get_uploads_playlist_id()
    videos = []
    next_page = None

    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page
        ).execute()

        for item in response["items"]:
            snippet = item["snippet"]
            videos.append({
                "video_id": snippet["resourceId"]["videoId"],
                "title": snippet["title"],
                "published_at": snippet["publishedAt"]
            })

        next_page = response.get("nextPageToken")
        if not next_page:
            break

    return videos

# ------------------------------------------
def save_videos_csv(videos):
    """Save video metadata, avoid duplicates"""
    existing_ids = set()
    if os.path.exists(VIDEOS_CSV):
        with open(VIDEOS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_ids = {row["video_id"] for row in reader}

    with open(VIDEOS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "title", "published_at"])
        if os.stat(VIDEOS_CSV).st_size == 0:
            writer.writeheader()
        for v in videos:
            if v["video_id"] not in existing_ids:
                writer.writerow(v)

# ------------------------------------------
def fetch_current_views(video_ids):
    """Fetch current views for a list of video IDs via YouTube API"""
    all_stats = []
    for i in range(0, len(video_ids), 50):
        chunk = ",".join(video_ids[i:i+50])
        response = youtube.videos().list(
            part="statistics",
            id=chunk
        ).execute()
        for item in response["items"]:
            all_stats.append({
                "video_id": item["id"],
                "current_views": int(item["statistics"].get("viewCount", 0))
            })
    return all_stats

# ------------------------------------------
def update_allvideoviews(api_callout):
    """
    Update allvideoviews.csv and calculate:
    - new views since last check
    - cumulative total views since tracking began
    """
    now = datetime.now().isoformat()
    existing = {}

    # Load existing allvideoviews.csv
    if os.path.exists(ALL_VIEWS_CSV):
        with open(ALL_VIEWS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["video_id"]] = {
                    "last_views": int(row["last_views"]),
                    "last_checked": row["last_checked"]
                }

    # Load previous cumulative total
    cumulative_total = 0
    if os.path.exists(SUMTOTAL_TXT):
        with open(SUMTOTAL_TXT, "r", encoding="utf-8") as f:
            try:
                cumulative_total = int(f.read().strip())
            except ValueError:
                cumulative_total = 0

    total_new_views = 0

    for video in api_callout:
        vid = video["video_id"]
        current_views = int(video["current_views"])

        if vid in existing:
            delta = max(0, current_views - existing[vid]["last_views"])
        else:
            # New video, all current views count as new
            delta = current_views

        total_new_views += delta
        cumulative_total += delta

        # Update/add video in existing dict
        existing[vid] = {
            "last_views": current_views,
            "last_checked": now
        }

    # Save updated allvideoviews.csv
    with open(ALL_VIEWS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "last_views", "last_checked"])
        writer.writeheader()
        for vid, data in existing.items():
            writer.writerow({
                "video_id": vid,
                "last_views": data["last_views"],
                "last_checked": data["last_checked"]
            })

    # Save cumulative total to sumtotal.txt
    with open(SUMTOTAL_TXT, "w", encoding="utf-8") as f:
        f.write(str(cumulative_total))

    print(f"📊 New views since last run: {total_new_views:,}")
    print(f"📈 Cumulative total views since tracking began: {cumulative_total:,}")

# ------------------------------------------
def start_server_and_open_browser():
    """Launch local web server and open dashboard in Chrome Beta"""
    print("🌐 Starting local web server...")
    subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1.5)
    print("🚀 Opening Chrome Beta dashboard...")
    subprocess.Popen([
        r"C:\Program Files\Google\Chrome Beta\Application\chrome.exe",
        "http://localhost:8000/views_progress.html"
    ])

# ------------------------------------------
# def run_once():
#     print("🔍 Discovering videos...")
#     videos = discover_videos()
#     save_videos_csv(videos)

#     video_ids = [v["video_id"] for v in videos]
#     print("📡 Fetching current views from API...")
#     api_callout = fetch_current_views(video_ids)

#     print("💾 Updating allvideoviews.csv and sumtotal.txt...")
#     update_allvideoviews(api_callout)


# ===================== RUN ==========================
if __name__ == "__main__":
    print("🚀 Starting automated view tracker (5-minute interval)")
    print("⛔ Press Ctrl+C to stop and open the dashboard")

    try:
        while True:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n⏱ Run started at {start_time}")

            # ---- main logic ----
            print("🔍 Discovering videos...")
            videos = discover_videos()
            save_videos_csv(videos)

            video_ids = [v["video_id"] for v in videos]
            print("📡 Fetching current views from API...")
            api_callout = fetch_current_views(video_ids)

            print("💾 Updating allvideoviews.csv and sumtotal.txt...")
            update_allvideoviews(api_callout)
            # --------------------

            print("✅ Run complete. Sleeping for 5 minutes...\n")
            time.sleep(300)  # 5 minutes

    except KeyboardInterrupt:
        print("\n🛑 Automation stopped by user.")
        print("🌐 Launching dashboard...")

        # Start server + browser ONLY on exit
        start_server_and_open_browser()

        print("✅ Dashboard opened. Script finished.")
