import os
import sqlite3

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/database.sqlite3'))
THUMBNAIL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/thumbnails'))

def repair_thumbnail_paths(db_path=DB_PATH, thumbnail_dir=THUMBNAIL_DIR):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Get all images with NULL or empty thumbnail_path
    cursor.execute("SELECT image_id, file_hash FROM images WHERE thumbnail_path IS NULL OR thumbnail_path = ''")
    images = cursor.fetchall()
    print(f"Found {len(images)} images with missing thumbnail_path.")
    updated = 0
    for image_id, file_hash in images:
        # Try to find a matching thumbnail file by hash (or by image_id if that's the convention)
        thumb_filename = None
        # Try by hash
        if file_hash:
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                candidate = f"{file_hash}{ext}"
                if os.path.isfile(os.path.join(thumbnail_dir, candidate)):
                    thumb_filename = candidate
                    break
        # Fallback: try by image_id
        if not thumb_filename:
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                candidate = f"{image_id}{ext}"
                if os.path.isfile(os.path.join(thumbnail_dir, candidate)):
                    thumb_filename = candidate
                    break
        if thumb_filename:
            cursor.execute("UPDATE images SET thumbnail_path = ? WHERE image_id = ?", (thumb_filename, image_id))
            updated += 1
            print(f"Updated image_id {image_id} with thumbnail {thumb_filename}")
    conn.commit()
    print(f"Updated {updated} images with thumbnail filenames.")
    conn.close()

if __name__ == "__main__":
    repair_thumbnail_paths()
