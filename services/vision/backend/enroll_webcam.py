"""
Enrol a student (or a teacher, for a live demo) straight from a webcam in about 30 seconds.

    python enroll_webcam.py EN-26-001 "Aarav Reddy"
    python enroll_webcam.py EN-26-001 "Aarav Reddy" --photos 10 --camera 0

Photos go to  NDB/<ID>_<Name>/ . Afterwards run   python db_make.py   once to build the face database
(it reads every folder in NDB/). Turn your head slightly between shots for better recognition.
Only enrol people who have given consent (for children: parent/guardian consent).
"""
import argparse
import os
import time

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("student_id", help="EduNest ID, e.g. EN-26-001")
    ap.add_argument("name", help='Full name, e.g. "Aarav Reddy"')
    ap.add_argument("--photos", type=int, default=8)
    ap.add_argument("--camera", default="0", help="webcam index or stream URL")
    ap.add_argument("--out", default=os.environ.get("INPUT_DATA_DIR", "NDB"))
    a = ap.parse_args()

    folder = os.path.join(a.out, f"{a.student_id}_{a.name}")
    os.makedirs(folder, exist_ok=True)
    cap = cv2.VideoCapture(int(a.camera) if a.camera.isdigit() else a.camera)
    if not cap.isOpened():
        raise SystemExit("Cannot open the camera.")
    print(f"Saving to {folder}\nSPACE = take photo (or wait: auto-capture every 1.5 s)   Q = quit")
    n, last = 0, time.time()
    while n < a.photos:
        ok, frame = cap.read()
        if not ok:
            continue
        view = frame.copy()
        cv2.putText(view, f"{a.name}: {n}/{a.photos}  (turn your head slightly)", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 220, 120), 2)
        cv2.imshow("Enrol - SPACE to capture, Q to quit", view)
        k = cv2.waitKey(30) & 0xFF
        if k == ord("q"):
            break
        if k == ord(" ") or time.time() - last > 1.5:
            cv2.imwrite(os.path.join(folder, f"{n:02d}.jpg"), frame)
            n += 1
            last = time.time()
    cap.release()
    cv2.destroyAllWindows()
    print(f"Saved {n} photos. Now run:  python db_make.py")


if __name__ == "__main__":
    main()
