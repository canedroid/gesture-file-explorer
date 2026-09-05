"""Gesture-Controlled Spatial HUD File Explorer - entry point.

Runs the full loop: camera capture, up to two virtual cursors, a window
manager owning independent floating cards, and the holographic renderer.
"""

import cv2

from camera import Camera
from gesture_control import Cursor
from hand_tracker import HandTracker
from spatial_window import STATE_DRAGGING
from window_manager import WindowManager
from window_renderer import WindowRenderer

WINDOW_NAME = "Gesture Spatial File Explorer"


def main():
    camera = Camera()
    tracker = HandTracker(max_hands=2)
    cursors = [Cursor(), Cursor()]
    manager = WindowManager()
    renderer = WindowRenderer()
    labels = ["HAND-1", "HAND-2"]

    manager.spawn_drives_card()
    manager.spawn_assistant_card()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    try:
        prev = {}
        vel = {}
        drag_owner = {}
        while True:
            frame = camera.read()
            if frame is None:
                print("[warn] Could not read frame from webcam.")
                continue

            try:
                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = tracker.find_hands(rgb_frame)
                height, width = frame.shape[:2]
                manager.set_viewport(width, height)

                hands = tracker.get_hands(results)
                for i, cursor in enumerate(cursors):
                    if i < len(hands):
                        label, landmarks = hands[i]
                        labels[i] = label
                        cursor.update(landmarks, width, height)
                    else:
                        cursor.update(None, width, height)
                order = [i for i, c in enumerate(cursors) if c.visible]

                # -- per-frame cursor velocity ---------------------------------
                for i, cursor in enumerate(cursors):
                    if cursor.visible:
                        px, py = prev.get(i, (cursor.x, cursor.y))
                        vel[i] = (cursor.x - px, cursor.y - py)
                        prev[i] = (cursor.x, cursor.y)
                    else:
                        prev.pop(i, None)
                        vel.pop(i, None)

                # -- dismiss via thumb-middle clamp ---------------------------
                for i in order:
                    if cursors[i].clamp_started:
                        win = manager.topmost_at(cursors[i].x, cursors[i].y)
                        if win is not None:
                            manager.close_window(win)

                # -- two-hand pinch scaling (takes priority) -------------------
                resize_win = None
                if (
                    len(order) == 2
                    and cursors[order[0]].is_pinched
                    and cursors[order[1]].is_pinched
                    and _same_window(manager, cursors[order[0]], cursors[order[1]])
                ):
                    resize_win = manager.topmost_at(
                        cursors[order[0]].x, cursors[order[0]].y
                    )
                if resize_win is not None:
                    a, b = cursors[order[0]], cursors[order[1]]
                    manager.apply_resize(resize_win, a.x, a.y, b.x, b.y)
                else:
                    manager.end_all_resizes()

                # -- pinch start: resolve actions ------------------------------
                if resize_win is None:
                    for i in order:
                        if cursors[i].pinch_started:
                            win = manager.topmost_at(cursors[i].x, cursors[i].y)
                            if win is not None:
                                action = manager.handle_pinch_start(
                                    win, cursors[i].x, cursors[i].y
                                )
                                if action["kind"] == "drag":
                                    drag_owner[i] = win
                                else:
                                    drag_owner.pop(i, None)
                            break

                # -- sustained drag following -------------------------------
                for i in order:
                    cursor = cursors[i]
                    if not cursor.is_pinched:
                        continue
                    win = manager.topmost_at(cursor.x, cursor.y)
                    if win is None or win.state != STATE_DRAGGING:
                        continue
                    drag_owner[i] = win
                    dx, dy = vel.get(i, (0.0, 0.0))
                    manager.move_drag(win, cursor.x, cursor.y, dx, dy)

                # -- release: flick closes, otherwise settle -----------------
                for i in range(len(cursors)):
                    cursor = cursors[i]
                    if not cursor.visible or cursor.is_pinched:
                        continue
                    vx, vy = vel.get(i, (0.0, 0.0))
                    win = drag_owner.pop(i, None)
                    if win is not None and win.state == STATE_DRAGGING:
                        manager.release_drag(win, vx, vy)

                manager.step_closing()

                # -- render -----------------------------------------------------
                renderer.render(frame, manager, cursors)
                for i in order:
                    cursors[i].draw(frame)

                status = (
                    "+".join(labels[i] for i in order) if order else "NO HAND"
                )
                cv2.putText(
                    frame,
                    status,
                    (15, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 240, 0),
                    1,
                    cv2.LINE_AA,
                )
            except Exception as exc:
                print(f"[error] frame pipeline failed: {exc}")

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        tracker.close()
        camera.release()
        cv2.destroyAllWindows()


def _same_window(manager, a, b):
    win_a = manager.topmost_at(a.x, a.y)
    win_b = manager.topmost_at(b.x, b.y)
    return win_a is not None and win_a is win_b


if __name__ == "__main__":
    main()