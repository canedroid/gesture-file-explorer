"""Webcam capture wrapper built on OpenCV."""

import cv2


class Camera:
    """Thin wrapper around cv2.VideoCapture for the default webcam."""

    def __init__(self, index=0, width=960, height=720):
        self.index = index
        self.capture = cv2.VideoCapture(index)
        if not self.capture.isOpened():
            raise RuntimeError(
                f"Unable to open video capture stream at index {index}."
            )
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    @property
    def is_opened(self):
        return self.capture.isOpened()

    def read(self):
        """Return a single raw BGR frame, or None when capture fails."""
        ok, frame = self.capture.read()
        if not ok:
            return None
        return frame

    def release(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()