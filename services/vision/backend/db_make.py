"""
Build the face database for Cerebromark / EduNest Smart Attendance.

Folder layout (the folder name MUST be  <EduNest student ID>_<Full Name>):
    NDB/
      EN-26-001_Aarav Reddy/   img1.jpg img2.jpg ... (8-10 photos, different angles)
      EN-26-002_Diya Sharma/   ...

Run:   python db_make.py            (CPU)       |   USE_GPU=1 python db_make.py
Output: New_face_db/<same folder names>/*.npy (+ cropped face jpgs)
Improvement over the original: only the LARGEST face in each photo is stored, so a
classmate standing in the background can never be enrolled under the wrong name.
"""
import os
import sys

import cv2
import numpy as np
import insightface
from tqdm import tqdm

INPUT_DIR = os.environ.get("INPUT_DATA_DIR", "NDB")
OUTPUT_DIR = os.environ.get("DB_PATH", "New_face_db")
MODEL_NAME = os.environ.get("MODEL_NAME", "buffalo_l")
USE_GPU = os.environ.get("USE_GPU", "0") == "1"


def main():
    if not os.path.isdir(INPUT_DIR):
        sys.exit(f"Input folder '{INPUT_DIR}' not found. Create it and add one sub-folder per student.")
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if USE_GPU else ["CPUExecutionProvider"]
    app = insightface.app.FaceAnalysis(name=MODEL_NAME, providers=providers)
    app.prepare(ctx_id=0 if USE_GPU else -1, det_size=(640, 640))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    people = [d for d in sorted(os.listdir(INPUT_DIR)) if os.path.isdir(os.path.join(INPUT_DIR, d))]
    print(f"Found {len(people)} students")
    for person in people:
        src, dst = os.path.join(INPUT_DIR, person), os.path.join(OUTPUT_DIR, person)
        os.makedirs(dst, exist_ok=True)
        saved = 0
        files = [f for f in os.listdir(src) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        for fn in tqdm(files, desc=person):
            img = cv2.imread(os.path.join(src, fn))
            if img is None:
                continue
            faces = app.get(img)
            if not faces:
                continue
            f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
            x1, y1, x2, y2 = [max(0, v) for v in f.bbox.astype(int)]
            np.save(os.path.join(dst, f"{person}_{saved}.npy"), f.embedding)
            crop = img[y1:y2, x1:x2]
            if crop.size:
                cv2.imwrite(os.path.join(dst, f"{person}_{saved}.jpg"), crop)
            saved += 1
        print(f"  -> {saved} faces saved for {person}" + ("   (add clearer photos!)" if saved < 4 else ""))
    print(f"\nDone. Database written to '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
