from base64 import b64encode
from re import S
from time import sleep
from typing import TYPE_CHECKING, ClassVar, Final

import chess
import numpy as np
from chess import BISHOP, BLACK, KING, KNIGHT, PAWN, QUEEN, ROOK, WHITE, Board, Move, Piece, square, square_name
from cv2 import (
    CAP_DSHOW,
    CAP_PROP_FPS,
    CAP_PROP_FRAME_HEIGHT,
    CAP_PROP_FRAME_WIDTH,
    CHAIN_APPROX_SIMPLE,
    COLOR_BGR2GRAY,
    FONT_HERSHEY_SIMPLEX,
    RETR_EXTERNAL,
    THRESH_BINARY,
    GaussianBlur,
    VideoCapture,
    absdiff,
    contourArea,
    cvtColor,
    findContours,
    getPerspectiveTransform,
    getTextSize,
    imencode,
    putText,
    rectangle,
    resize,
    threshold,
    warpPerspective,
)
from cv2.aruco import (
    DICT_4X4_50,
    ArucoDetector,
    DetectorParameters,
    Dictionary,
    extendDictionary,
    getPredefinedDictionary,
)
from cv2.typing import MatLike
from flet import FilterQuality, Image
from numpy import array, float32, int32, mean, zeros

if TYPE_CHECKING:
    from numpy.typing import NDArray
if TYPE_CHECKING:
    from numpy.typing import NDArray


class ImageProcessing:
    DICT: Dictionary = extendDictionary(14, 4, getPredefinedDictionary(DICT_4X4_50))
    PARAMS: DetectorParameters = DetectorParameters()
    DETECTOR: ArucoDetector = ArucoDetector(DICT, PARAMS)
    PIECE_IDS: ClassVar[dict[int, Piece]] = {
        2: Piece(PAWN, WHITE),
        3: Piece(PAWN, BLACK),
        4: Piece(ROOK, WHITE),
        5: Piece(ROOK, BLACK),
        6: Piece(QUEEN, WHITE),
        7: Piece(QUEEN, BLACK),
        8: Piece(KING, WHITE),
        9: Piece(KING, BLACK),
        10: Piece(BISHOP, WHITE),
        11: Piece(BISHOP, BLACK),
        12: Piece(KNIGHT, WHITE),
        13: Piece(KNIGHT, BLACK),
    }

    def __init__(self, frame_size: int, perspective_offset: int) -> None:
        self.__middle_point: NDArray[int32] = array([0, 0], dtype=int32)
        self.__corner_point_1: NDArray[int32] = array([0, 0], dtype=int32)
        self.__corner_point_2: NDArray[int32] = array([0, 0], dtype=int32)
        self.__frame_size: Final[int] = frame_size
        self.__perspective_offset: Final[int] = perspective_offset
        self.__perspective_destination: Final[NDArray[float32]] = array(
            [
                [-self.__perspective_offset, -self.__perspective_offset],
                [
                    self.__frame_size + self.__perspective_offset,
                    -self.__perspective_offset,
                ],
                [
                    -self.__perspective_offset,
                    self.__frame_size + self.__perspective_offset,
                ],
                [
                    self.__frame_size + self.__perspective_offset,
                    self.__frame_size + self.__perspective_offset,
                ],
            ],
            dtype=np.float32,
        )
        self.__perspective_source: NDArray[float32] = array([[0, 0], [0, 0], [0, 0], [0, 0]], dtype=float32)
        self.__square_cords: frozenset[tuple[int, int, int, int, int]] = frozenset(
            (
                x * self.__frame_size // 8 - 5,
                y * self.__frame_size // 8 - 5,
                (x + 1) * self.__frame_size // 8 + 5,
                (y + 1) * self.__frame_size // 8 + 5,
                (square(x, 7 - y)),
            )
            for x in range(8)
            for y in range(8)
        )
        self.__prev_gray: MatLike = np.zeros((self.__frame_size, self.__frame_size), dtype=np.uint8)
        self.__white_board: Board = Board(fen="8/8/8/8/8/8/PPPPPPPP/RNBQKBNR")
        self.__black_board: Board = Board(fen="rnbqkbnr/pppppppp/8/8/8/8/8/8")
        self.__piece_count: int = 16
        self.__counter: int = 0

    def is_stable(self, frame: MatLike) -> bool:
        gray_frame = cvtColor(frame, COLOR_BGR2GRAY)
        blur_frame = GaussianBlur(gray_frame, (5, 5), 0)
        if self.__prev_gray.shape != blur_frame.shape:
            blur_frame = resize(blur_frame, (self.__prev_gray.shape[1], self.__prev_gray.shape[0]))
        difference = absdiff(self.__prev_gray, blur_frame)
        thresh = threshold(difference, 15, 255, THRESH_BINARY)[1]
        contours = findContours(thresh, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)[0]
        movement_detected = any(contourArea(contour) > 300 for contour in contours)
        self.__prev_gray = blur_frame.copy()
        return not movement_detected

    def get_chessboard(self, frame: MatLike) -> MatLike:
        detected_markers: tuple = self.DETECTOR.detectMarkers(frame)
        if detected_markers[1] is None or any({0, 1}) not in detected_markers[1]:
            return frame
        if all({0, 1}) in detected_markers[1].flatten():
            self.__corner_point_1 = detected_markers[0][list(detected_markers[1]).index(0)].reshape((4, 2)).astype(int)[1]
            self.__corner_point_2 = detected_markers[0][list(detected_markers[1]).index(1)].reshape((4, 2)).astype(int)[3]
            self.__middle_point = mean([self.__corner_point_1, self.__corner_point_2], axis=0).astype(int)
            self.__perspective_source = array(
                [
                    [
                        self.__middle_point[0] - self.__corner_point_1[1] + self.__middle_point[1],
                        self.__middle_point[1] + self.__corner_point_1[0] - self.__middle_point[0],
                    ],
                    [
                        2 * self.__middle_point[0] - self.__corner_point_1[0],
                        2 * self.__middle_point[1] - self.__corner_point_1[1],
                    ],
                    [self.__corner_point_1[0], self.__corner_point_1[1]],
                    [
                        self.__middle_point[0] + self.__corner_point_1[1] - self.__middle_point[1],
                        self.__middle_point[1] - self.__corner_point_1[0] + self.__middle_point[0],
                    ],
                ],
                dtype=np.float32,
            )
        return warpPerspective(
            frame,
            getPerspectiveTransform(self.__perspective_source, self.__perspective_destination),
            (self.__frame_size, self.__frame_size),
        )

    def get_piece_board(self, frame: MatLike, color: chess.Color) -> Board:
        board = Board(fen=None)
        detected_markers: tuple = self.DETECTOR.detectMarkers(frame)
        if detected_markers[1] is None:
            return board
        for marker_corner, marker_id in zip(detected_markers[0], detected_markers[1].flatten(), strict=True):
            if marker_id not in self.PIECE_IDS:
                continue
            if self.PIECE_IDS[marker_id].color != color:
                continue
            corners: NDArray[int32] = marker_corner.reshape((4, 2)).astype(int)
            center = tuple(mean([corners[0], corners[2]], axis=0).astype(int))
            for cord in self.__square_cords:
                if cord[0] < center[0] < cord[2] and cord[1] < center[1] < cord[3]:
                    board.set_piece_at(cord[4], self.PIECE_IDS[marker_id])
        return board

    def get_move(self, frame: MatLike, color: chess.Color) -> Move | None:
        self.__counter += 1
        new_board = self.get_piece_board(frame, color).piece_map()
        if self.__counter < 30:
            return None
        self.__counter = 0
        if (
            not self.is_stable(frame)
            or len(self.__white_board.piece_map() if color else self.__black_board.piece_map()) != self.__piece_count
            or len(new_board) != self.__piece_count
            or new_board == (self.__white_board.piece_map() if color else self.__black_board.piece_map())
        ):
            return None
        if self.__white_board.piece_map() if color else self.__black_board.piece_map() != new_board:
            from_square = self.__white_board.piece_map().items() - new_board.items() if color else self.__black_board.piece_map().items() - new_board.items()
            to_square = new_board.items() - (self.__white_board.piece_map().items() if color else self.__black_board.piece_map().items())
            if len(from_square) != 1 or len(to_square) != 1:
                return None
            self.__white_board.set_piece_map(new_board) if color else self.__black_board.set_piece_map(new_board)
            return Move.from_uci(f"{square_name(next(iter(from_square))[0])}{square_name(next(iter(to_square))[0])}")
        return None

    def push_capture(self, move: Move, color: chess.Color) -> None:
        self.__piece_count -= 1
        self.__white_board.remove_piece_at(move.to_square) if color else self.__black_board.remove_piece_at(move.to_square)
