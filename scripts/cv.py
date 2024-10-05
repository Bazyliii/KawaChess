import cv2
import numpy as np

images = [cv2.imread(f"board_moves/flat/{i}.png") for i in range(18)]


i = 0

while 1:
    frame = images[i]
    frame = cv2.blur(frame, (3, 3))
    cv2.threshold(frame, 125, 255, cv2.THRESH_BINARY, frame)
    cv2.imshow("image", frame)

    if cv2.waitKey(1000) & 0xFF == ord("q"):
        break
    i += 1
    if i == 17:
        i = 0



if __name__ == "__main__":
    ...
