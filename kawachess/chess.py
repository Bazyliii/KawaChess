from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Final

import chess
from chess import Board, svg
from chess import Move as Chess_Move
from chess.engine import Limit, SimpleEngine
from cv2 import (
    CAP_DSHOW,
    CAP_PROP_FPS,
    CAP_PROP_FRAME_HEIGHT,
    CAP_PROP_FRAME_WIDTH,
    VideoCapture,
)
from flet import Column, Control, CrossAxisAlignment, Icons, Image, MainAxisAlignment, Row
from pytz import BaseTzInfo, timezone

from kawachess.astemplates import en_passant, kingside_castling, move_with_capture, move_without_capture, queenside_castling
from kawachess.components import Button
from kawachess.constants import ACCENT_COLOR_1, ACCENT_COLOR_2, ACCENT_COLOR_3, ACCENT_COLOR_4, WHITE
from kawachess.database import ChessDatabase, GameData
from kawachess.gripper import Gripper, State
from kawachess.robot import Cartesian, Move, Point, Program, Robot, Switch
from kawachess.vision import ImageProcessing

TIMEZONE: Final[BaseTzInfo] = timezone("Europe/Warsaw")


class GameContainer(Column):
    def __init__(self, board_size: int, dialog: Callable[[str], None], robot: Robot) -> None:
        super().__init__()
        self.base: Point = Point("base", Cartesian(x=134.255, y=554.503, z=-201.167, o=-175.344, a=179.571, t=-86.117))
        self.A1: Point = self.calculate_point_to_move("a1", 80)
        self.A8: Point = self.calculate_point_to_move("a8", 80)
        self.E1: Point = self.calculate_point_to_move("e1", 80)
        self.E8: Point = self.calculate_point_to_move("e8", 80)
        self.G1: Point = self.calculate_point_to_move("g1", 80)
        self.G8: Point = self.calculate_point_to_move("g8", 80)
        self.H1: Point = self.calculate_point_to_move("h1", 80)
        self.H8: Point = self.calculate_point_to_move("h8", 80)
        self.F1: Point = self.calculate_point_to_move("f1", 80)
        self.F8: Point = self.calculate_point_to_move("f8", 80)
        self.C1: Point = self.calculate_point_to_move("c1", 80)
        self.C8: Point = self.calculate_point_to_move("c8", 80)
        self.D1: Point = self.calculate_point_to_move("d1", 80)
        self.D8: Point = self.calculate_point_to_move("d8", 80)
        self.drop: Point = Point("drop", Cartesian(x=332.127, y=275.956, z=-116.837, o=-175.344, a=179.571, t=-86.117))
        self.dialog: Callable[[str], None] = dialog
        self.robot: Robot = robot
        self.gripper: Gripper = Gripper(dialog=dialog)
        self.__skill_level: int
        self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
        self.__engine.configure({"Threads": "2", "Hash": "512"})
        self.__game_status: bool = False
        self.__start_datetime: datetime
        self.__pending_game_stockfish_skill_lvl: int
        self.__image_processing: ImageProcessing = ImageProcessing(720, -5)
        self.__capture: VideoCapture = VideoCapture(0, CAP_DSHOW)
        self.__capture.set(CAP_PROP_FPS, 30)
        self.__capture.set(CAP_PROP_FRAME_HEIGHT, 720)
        self.__capture.set(CAP_PROP_FRAME_WIDTH, 1280)
        self.__board_colors: dict[str, str] = {
            "square light": "#DDDDDD",
            "square dark": ACCENT_COLOR_1,
            "margin": ACCENT_COLOR_2,
            "coord": WHITE,
            "square light lastmove": ACCENT_COLOR_4,
            "square dark lastmove": ACCENT_COLOR_3,
        }
        self.board: Board = Board()
        self.__chess_board_svg: Image = Image(svg.board(self.board, colors=self.__board_colors), width=board_size, height=board_size)
        self.__player_name: str
        self.__player_color: chess.Color = chess.BLACK
        self.expand = True
        self.bgcolor: str = ACCENT_COLOR_1
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.visible = True
        self.spacing = 50
        self.__is_mounted = False
        self.__start_button = Button(text="Start game", on_click=self.start_game, icon=Icons.PLAY_ARROW_OUTLINED, disabled=False)
        self.__resign_button = Button(text="Resign game", on_click=self.resign_game, icon=Icons.HANDSHAKE_OUTLINED, disabled=True)
        self.controls = [
            Row(
                [
                    self.__chess_board_svg,
                    # self.__opencv_detection,
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
            Row(
                [
                    self.__start_button,
                    self.__resign_button,
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
        ]

    def start_game(self, *_: object) -> None:
        if not self.robot.logged_in:
            self.dialog("Connect to robot first!")
            return
        self.__start_button.disabled = True
        self.__resign_button.disabled = False
        self.__start_button.update()
        self.__resign_button.update()
        self.__game_status = True
        self.robot.add_point(
            self.A1, self.A8, self.E1, self.E8, self.G1, self.G8, self.H1, self.H8, self.F1, self.F8, self.C1, self.C8, self.D1, self.D8, self.drop
        )
        self.robot.move(Move.HYBRID, self.drop)
        player_turn: bool = self.__player_color
        self.board.reset()
        self.__engine.configure({"Skill Level": self.__skill_level})
        self.__start_datetime = datetime.now(TIMEZONE)
        self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors)
        self.update_when_mounted(self.__chess_board_svg)
        self.__pending_game_stockfish_skill_lvl = self.__skill_level
        while self.__game_status and not self.board.is_game_over():
            if not player_turn:
                engine_move: Chess_Move | None = self.__engine.play(self.board, Limit(time=1.0)).move
                if engine_move is None or engine_move not in self.board.legal_moves:
                    continue
                if engine_move.promotion:
                    print(engine_move)
                self.make_move(engine_move)
                if self.__game_status:
                    self.board.push(engine_move)
                    self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=engine_move)
                self.update_when_mounted(self.__chess_board_svg)
                player_turn = True

            while player_turn and self.__game_status and not self.board.is_game_over():
                frame = self.__capture.read()[1]
                chess_board = self.__image_processing.get_chessboard(frame)
                move = self.__image_processing.get_move(chess_board, self.__player_color)
                if move:
                    self.board.push(move)
                    self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=move)
                    self.update_when_mounted(self.__chess_board_svg)
                    player_turn = False
        game_data = GameData(
            self.board,
            self.__pending_game_stockfish_skill_lvl,
            self.__start_datetime,
            datetime.now(TIMEZONE),
            ("Stockfish", self.__player_name),
        )
        with ChessDatabase("chess.db") as database:
            database.add(game_data)
        self.__game_status = False
        self.__start_button.disabled = False
        self.__resign_button.disabled = True
        self.__start_button.update()
        self.__resign_button.update()
        if self.board.is_game_over():
            self.__image_processing.clear_boards()
            self.dialog("Game over!")
        self.update_when_mounted(self.__chess_board_svg)

    def make_move(self, move: Chess_Move, speed: int = 10, height: int = 80) -> None:
        from_point: Point = self.calculate_point_to_move(move.uci()[0:2], height)
        to_point: Point = self.calculate_point_to_move(move.uci()[2:4], height)
        self.robot.add_point(from_point, to_point)
        if self.board.is_capture(move):
            self.__image_processing.push_capture(move, self.__player_color)
            if self.board.is_en_passant(move):
                take_point: Point = self.calculate_point_to_move(move.uci()[2] + move.uci()[1], height)
                self.robot.add_point(take_point)
                self.execute_task(en_passant(from_point, to_point, take_point, self.drop, speed, height))
                return
            self.execute_task(move_with_capture(from_point, to_point, self.drop, speed, height))
            return
        if self.board.is_kingside_castling(move):
            self.execute_task(kingside_castling(self.drop, self.board.turn, speed, height))
            return
        if self.board.is_queenside_castling(move):
            self.execute_task(queenside_castling(self.drop, self.board.turn, speed, height))
            return
        self.execute_task(move_without_capture(from_point, to_point, self.drop, speed, height))

    def execute_task(self, tasks: tuple[Program | State, ...]) -> None:
        for task in tasks:
            if type(task) is State:
                self.gripper.control(task)
            elif type(task) is Program:
                self.robot.load_program(task)
                self.robot.exec_program(task)

    def resign_game(self, *_: object) -> None:
        if not self.__game_status:
            return
        # self.robot.abort_motion()
        self.__game_status = False
        self.__image_processing.clear_boards()
        self.__resign_button.disabled = True
        self.__start_button.disabled = False
        self.__resign_button.update()
        self.__start_button.update()
        self.dialog("Player resigned!")

    def close(self) -> None:
        if self.__game_status:
            self.__game_status = False
            self.robot.abort_motion()
        # self.__opencv_detection.close()
        self.__engine.quit()

    def did_mount(self) -> None:
        self.__is_mounted = True

    def will_unmount(self) -> None:
        self.__is_mounted = False

    def update_when_mounted(self, control: Control) -> None:
        if self.__is_mounted:
            control.update()

    def calculate_point_to_move(self, algebraic_move: str, z: float = 0.0) -> Point:
        x: int = ord(algebraic_move[0].lower()) - ord("a")
        y: int = int(algebraic_move[1]) - 1
        return self.base.shift(algebraic_move, Cartesian(x=x * -37.3, y=y * -37.3, z=z))

    @property
    def player_name(self) -> str:
        return self.__player_name

    @player_name.setter
    def player_name(self, player_name: str) -> None:
        self.__player_name: str = player_name

    @property
    def skill_level(self) -> int:
        return self.__skill_level

    @skill_level.setter
    def skill_level(self, skill_level: int) -> None:
        self.__skill_level: int = skill_level

    @property
    def player_color(self) -> str | None:
        match self.__player_color:
            case chess.WHITE:
                return "white"
            case chess.BLACK:
                return "black"
            case _:
                return None

    @player_color.setter
    def player_color(self, player_color: str) -> None:
        match player_color:
            case "white":
                self.__player_color = chess.WHITE
            case "black":
                self.__player_color = chess.BLACK