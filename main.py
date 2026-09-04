"""Gesture-Controlled Virtual AR File Explorer - entry point."""

import cv2

from camera import Camera
from file_engine import FileEntry, get_drives
from gesture_control import Cursor
from hand_tracker import HandTracker
from ui_overlay import HUD


def root_entries():
    return [
        FileEntry(name=drive, path=drive, is_dir=True) for drive in get_drives()
    ]


def main():
    camera = Camera()
    tracker = HandTracker()
    cursor = Cursor()
    hud = HUD()
    entries = root_entries()

    window_name = "Gesture File Explorer"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            frame = camera.read()
            if frame is None:
                print("[warn] Could not read frame from webcam.")
                continue

            # Mirror horizontally for a natural selfie-style view.
            frame = cv2.flip(frame, 1)

            # Convert BGR to RGB for MediaPipe processing.
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = tracker.find_hands(rgb_frame)
            tracker.draw_landmarks(frame, results)

            height, width = frame.shape[:2]
            landmarks = tracker.get_landmarks(results)
            cursor.update(landmarks, width, height)

            hud.render(
                frame,
                "GESTURE FILE EXPLORER",
                "This PC",
                entries,
                cursor=cursor,
            )
            cursor.draw(frame)

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        tracker.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()