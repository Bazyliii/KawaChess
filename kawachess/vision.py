from base64 import b64encode
from time import sleep
from typing import TYPE_CHECKING

from cv2 import CAP_PROP_FPS, VideoCapture, imencode, resize
from flet import FilterQuality, Image

if TYPE_CHECKING:
    from numpy.typing import NDArray


class OpenCVDetection(Image):
    def __init__(self, image_size: int) -> None:
        super().__init__()
        self.capture: VideoCapture = VideoCapture(0)
        self.image_size: int = image_size
        self.width = self.height = self.image_size
        self.filter_quality = FilterQuality.NONE

    def did_mount(self) -> None:
        if not self.capture.isOpened() or self.capture.get(CAP_PROP_FPS) == 0:
            self.src = "no_camera.png"
            self.update()
            return
        frame: NDArray = self.capture.read()[1]
        frame_shape: tuple = frame.shape
        x: int = frame_shape[1] // 2
        y: int = frame_shape[0] // 2
        margin: int = min(x, y)
        left: int = x - margin
        right: int = x + margin
        bottom: int = y + margin
        top: int = y - margin
        delay: float = 0.5 / self.capture.get(CAP_PROP_FPS)
        while self.capture.isOpened():
            frame = self.capture.read()[1]
            resized_frame: NDArray = resize(frame[top:bottom, left:right], (self.image_size, self.image_size))
            self.src_base64 = b64encode(imencode(".bmp", resized_frame)[1]).decode("utf-8")
            self.update()
            sleep(delay)

    def build(self) -> None:
        self.img = Image(height=self.image_size, width=self.image_size)

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        self.capture.release()
