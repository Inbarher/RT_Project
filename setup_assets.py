from PIL import Image
import os


def create_all_qualities():
    # רשימת הסרטים והפריימים שיצרת מהמצגת
    movies = {
        "Circle": ["frame_1.png", "frame_2.png", "frame_3.png"],
        "Triangle": ["frame_1.png", "frame_2.png", "frame_3.png"]
    }

    base_path = "Movies"

    for movie, frames in movies.items():
        for frame_name in frames:
            # נתיב לקובץ המקור (שנמצא בתיקיית High)
            source_path = os.path.join(base_path, movie, "High", frame_name)

            if not os.path.exists(source_path):
                print(f"Warning: Could not find source {source_path}")
                continue

            img = Image.open(source_path)
            w, h = img.size

            # יצירת איכות בינונית (Med) - 50% מהגודל
            med_path = os.path.join(base_path, movie, "Med", frame_name)
            img.resize((w // 2, h // 2)).save(med_path)

            # יצירת איכות נמוכה (Low) - 25% מהגודל
            low_path = os.path.join(base_path, movie, "Low", frame_name)
            img.resize((w // 4, h // 4)).save(low_path)

            print(f"Processed qualities for {movie} - {frame_name}")


if __name__ == "__main__":
    # ודאי שהתמונות המקוריות כבר נמצאות בתיקיות ה-High לפני ההרצה
    create_all_qualities()