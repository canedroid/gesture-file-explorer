"""Gesture-Controlled Virtual AR File Explorer - entry point."""

import cv2

from app import ExplorerApp
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
        total_rows = 0
        visible_rows = 0
        while True:
            frame = camera.read()
            if frame is None:
                print("[warn] Could not read frame from webcam.")
                continue

            try:
                # Mirror horizontally for a natural selfie-style view.
                frame = cv2.flip(frame, 1)

                # Convert BGR to RGB for MediaPipe processing.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                results = tracker.find_hands(rgb_frame)
                tracker.draw_landmarks(frame, results)

                height, width = frame.shape[:2]
                landmarks = tracker.get_landmarks(results)
                cursor.update(landmarks, width, height)

                if app.is_file_view:
                    total_rows = app._wrapped_count
                else:
                    total_rows = len(app.entries)
                visible_rows = hud.visible_rows
                page = max(1, visible_rows)

                # Pager button pinch.
                button = (
                    hud.pager_button_at(cursor.x, cursor.y)
                    if cursor.visible
                    else None
                )
                if cursor.pinch_started and button:
                    delta = -page if button == "up" else page
                    app.scroll_page(delta, total_rows, visible_rows)
                    app.end_drag()
                elif cursor.pinch_started:
                    hover = hud.hovered_index(cursor, width, height)
                    if hover is not None:
                        if app.is_file_view:
                            if hover == 0:
                                app.activate_index(0)
                                app.end_drag()
                        else:
                            app.activate_index(app.scroll_offset + hover)
                            app.end_drag()

                # Pinch-drag scrolling inside the file viewer content area.
                hover = hud.hovered_index(cursor, width, height)
                dragging_area = app.is_file_view and hover is not None and hover > 0
                if cursor.is_pinched and dragging_area:
                    app.drag_to(
                        cursor.y,
                        max(1, hud.row_height - 16),
                        app._wrapped_count,
                        hud.visible_rows,
                    )
                else:
                    app.end_drag()

                if app.is_file_view:
                    wrapped_count = hud.render_text(
                        frame,
                        "FILE VIEW",
                        app.directory_label,
                        app.lines,
                        scroll_line=app.scroll_offset,
                        cursor=cursor,
                    )[1]
                    app._wrapped_count = wrapped_count
                    if app.scroll_offset > max(
                        0, wrapped_count - hud.visible_rows
                    ):
                        app.scroll_to(
                            app.scroll_offset,
                            wrapped_count,
                            hud.visible_rows,
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
            except Exception as exc:
                print(f"[error] frame pipeline failed: {exc}")

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("w"):
                app.scroll_page(-page, total_rows, visible_rows)
            elif key == ord("s"):
                app.scroll_page(page, total_rows, visible_rows)
    finally:
        tracker.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()