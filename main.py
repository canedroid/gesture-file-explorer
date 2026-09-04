"""Gesture-Controlled Virtual AR File Explorer - entry point."""

import cv2

from app import ExplorerApp, ViewState
from camera import Camera
from gesture_control import Cursor
from hand_tracker import HandTracker
from ui_overlay import HUD


def main():
    camera = Camera()
    tracker = HandTracker()
    cursor = Cursor()
    hud = HUD()
    app = ExplorerApp()

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

            if cursor.pinch_started:
                hover = hud.hovered_index(cursor, width, height)
                if hover is not None:
                    if app.is_file_view:
                        app.activate_index(hover)
                    else:
                        app.activate_index(app.scroll_offset + hover)

            if app.is_file_view:
                hud.render_text(
                    frame,
                    "FILE VIEW",
                    app.directory_label,
                    app.lines,
                    scroll_line=app.scroll_offset,
                    cursor=cursor,
                )
            else:
                hud.render(
                    frame,
                    "GESTURE FILE EXPLORER",
                    app.directory_label,
                    app.entries,
                    cursor=cursor,
                    scroll_offset=app.scroll_offset,
                )

            if app.error_message:
                cv2.putText(
                    frame,
                    "ERR: " + app.error_message[:70],
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
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