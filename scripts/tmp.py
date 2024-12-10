from cv2 import VideoCapture, imshow, waitKey
from numpy import ndarray

capture = VideoCapture(0)

while True:
    frame: ndarray = capture.read()[1]
    center = frame.shape
    print(type(center[1]))
    y: int = center[0] // 2
    x: int = center[1] // 2
    margin: int = min(x,y)
    cropped_frame = frame[y-margin:y+margin, x-margin:x+margin]
    imshow("frame", cropped_frame)
    imshow("frame2", frame)
    if waitKey(1) == ord('q'):
        break
