import cv2
import dxcam
import numpy as np
from dxcam import DXCamera
from numpy import ndarray

screen_capture: DXCamera = dxcam.create(device_idx=0, output_idx=1, output_color="BGR")
screen_capture.start(target_fps=60, video_mode=True)

initial: ndarray = np.array([])
finall: ndarray = np.array([])
diff: ndarray = np.array([])
while True:
	frame: ndarray = screen_capture.get_latest_frame()
	blur: ndarray = cv2.blur(frame, (2, 2))
	gray: ndarray = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
	edges: ndarray = cv2.Canny(gray, 50, 150, apertureSize=3)
	contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	chessboard_contour = None
	max_area = 0
	for contour in contours:
		epsilon = 0.1 * cv2.arcLength(contour, True)
		approx = cv2.approxPolyDP(contour, epsilon, True)
		if len(approx) == 4:
			area = cv2.contourArea(contour)
			if area > max_area:
				chessboard_contour = approx
				max_area = area
	if chessboard_contour is None:
		print("Nie znaleziono planszy do szachów")
	else:
		cv2.drawContours(frame, [chessboard_contour], -1, (0, 255, 0), 2)
		points = chessboard_contour.reshape(4, 2)
		rect = np.zeros((4, 2), dtype="float32")
		s = points.sum(axis=1)
		rect[0] = points[np.argmin(s)]
		rect[2] = points[np.argmax(s)]
		diff = np.diff(points, axis=1)
		rect[1] = points[np.argmin(diff)]
		rect[3] = points[np.argmax(diff)]
		(tl, tr, br, bl) = rect

		for i in range(1, 8):
			# Pionowe linie
			start_x = int(tl[0] + (tr[0] - tl[0]) * i / 8)
			start_y = int(tl[1] + (tr[1] - tl[1]) * i / 8)
			end_x = int(bl[0] + (br[0] - bl[0]) * i / 8)
			end_y = int(bl[1] + (br[1] - bl[1]) * i / 8)
			cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2)

			# Poziome linie
			start_x = int(tl[0] + (bl[0] - tl[0]) * i / 8)
			start_y = int(tl[1] + (bl[1] - tl[1]) * i / 8)
			end_x = int(tr[0] + (br[0] - tr[0]) * i / 8)
			end_y = int(tr[1] + (br[1] - tr[1]) * i / 8)
			cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2)

	cv2.imshow("Chessboard with Grid", frame)
	if cv2.waitKey(1) & 0xFF == ord("s"):
		print("Start")  # <- Sygnał z zegara
		start_frame = frame
	if cv2.waitKey(1) & 0xFF == ord("d"):
		print("Ruch wykonany")  # <- Sygnał z zegara
		finall = frame
  
	if cv2.waitKey(1) & 0xFF == ord("q"):
		break
