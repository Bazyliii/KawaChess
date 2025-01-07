from collections.abc import Callable
from datetime import datetime
from typing import Final

from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from flet import Column, CrossAxisAlignment, Icons, Image, MainAxisAlignment, Row
from pytz import BaseTzInfo, timezone

from kawachess.astemplates import en_passant, kingside_castling, move_with_capture, move_without_capture, queenside_castling
from kawachess.colors import ACCENT_COLOR_1, ACCENT_COLOR_2, ACCENT_COLOR_3, ACCENT_COLOR_4, WHITE
from kawachess.components import Button
from kawachess.database import ChessDatabase, GameData
from kawachess.robot import Cartesian, Command, Point, Program, Robot
from kawachess.vision import OpenCVDetection

TIMEZONE: Final[BaseTzInfo] = timezone("Europe/Warsaw")


class GameContainer(Column):
    def __init__(self, board_size: int, dialog: Callable[[str], None], robot: Robot) -> None:
        super().__init__()
        self.A1: Point = Point("a1", Cartesian(91.362, 554.329, -193.894, -137.238, 179.217, -5.03))
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
        self.drop: Point = Point("drop", Cartesian(300.362, 448.329, -93.894, -137.238, 179.217, -5.03))
        self.dialog: Callable[[str], None] = dialog
        self.robot: Robot = robot
        self.__skill_level: int
        self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
        self.__engine.configure({"Threads": "2", "Hash": "512"})
        self.__game_status: bool = False
        self.__start_datetime: datetime
        self.__pending_game_stockfish_skill_lvl: int
        self.__opencv_detection: OpenCVDetection = OpenCVDetection(board_size)
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
        self.expand = True
        self.bgcolor: str = ACCENT_COLOR_1
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.visible = True
        self.spacing = 50
        self.controls = [
            Row(
                [
                    self.__chess_board_svg,
                    self.__opencv_detection,
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
            Row(
                [
                    Button(
                        text="Start game",
                        on_click=lambda _: self.start_game(),
                        icon=Icons.PLAY_ARROW_OUTLINED,
                    ),
                    Button(
                        text="Resign game",
                        on_click=lambda _: self.resign_game(),
                        icon=Icons.HANDSHAKE_OUTLINED,
                    ),
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
        ]

    def start_game(self) -> None:
        if not self.robot.logged_in:
            self.dialog("Connect to robot first!")
            return
        if self.__game_status:
            return
        self.robot.add_translation_point(
            self.A1,
            self.A8,
            self.E1,
            self.E8,
            self.G1,
            self.G8,
            self.H1,
            self.H8,
            self.F1,
            self.F8,
            self.C1,
            self.C8,
            self.D1,
            self.D8,
            self.drop,
        )
        player_turn: bool = False
        STARTING_BOARD_FEN = "r1b1kb1r/3pnppp/1Qp1p3/4P3/p1P1B3/P5P1/1P3P1P/2B1R1K1"
        self.board.reset()
        self.board.set_fen(STARTING_BOARD_FEN)
        self.__engine.configure({"Skill Level": self.__skill_level})
        self.__start_datetime = datetime.now(TIMEZONE)
        self.__game_status = True
        self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors)
        self.update()
        self.__pending_game_stockfish_skill_lvl = self.__skill_level
        self.board.push_uci("e1d1")
        self.board.push_uci("f7f5")
        while self.__game_status and not self.board.is_game_over():
            engine_move: Move | None = self.__engine.play(self.board, Limit(time=1.0)).move
            if engine_move is None or engine_move not in self.board.legal_moves:
                continue

            program: Program = self.get_move_program(engine_move)
            self.robot.load_as_program(program)
            self.robot.exec_as_program(program)

            if self.__game_status:
                self.board.push(engine_move)
                self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=engine_move)
            self.update()
            player_turn = False
            # self.dialog("Player move")
            while player_turn:
                try:
                    player_move: Move = Move.from_uci(input("Enter move: "))
                except ValueError:
                    self.dialog("Invalid move")
                    continue
                if player_move in self.board.legal_moves:
                    self.board.push(player_move)
                    self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=player_move)
                    self.update()
                    player_turn = False
                else:
                    self.dialog("Invalid move")
        game_data = GameData(
            self.board, self.__pending_game_stockfish_skill_lvl, self.__start_datetime, datetime.now(TIMEZONE), ("Stockfish", self.__player_name)
        )
        with ChessDatabase("chess.db") as database:
            database.add(game_data)
        self.__game_status = False
        if self.board.is_game_over():
            self.dialog("Game over!")
        self.update()

    def get_move_program(self, move: Move, speed: int = 5, height: int = 80) -> Program:
        from_point: Point = self.calculate_point_to_move(move.uci()[0:2], height)
        to_point: Point = self.calculate_point_to_move(move.uci()[2:4], height)
        self.robot.add_translation_point(from_point, to_point)
        if self.board.is_capture(move):
            if self.board.is_en_passant(move):
                take_point: Point = self.calculate_point_to_move(move.uci()[2] + move.uci()[1], height)
                self.robot.add_translation_point(take_point)
                return en_passant(from_point, to_point, take_point, self.drop, speed, height)
            return move_with_capture(from_point, to_point, self.drop, speed, height)
        if self.board.is_kingside_castling(move):
            return kingside_castling(self.drop, self.board.turn, speed, height)
        if self.board.is_queenside_castling(move):
            return queenside_castling(self.drop, self.board.turn, speed, height)
        return move_without_capture(from_point, to_point, self.drop, speed, height)

    def resign_game(self) -> None:
        if not self.__game_status:
            return
        self.robot.send(Command.ABORT)
        self.__game_status = False
        self.dialog("Player resigned!")

    def close(self) -> None:
        if self.__game_status:
            self.__game_status = False
            self.robot.send(Command.ABORT)
        self.__opencv_detection.close()
        self.__engine.quit()

    def calculate_point_to_move(self, algebraic_move: str, z: float = 0.0) -> Point:
        x: int = ord(algebraic_move[0]) - ord("a")
        y: int = int(algebraic_move[1]) - 1
        return self.A1.shift(algebraic_move, Cartesian(x=x * -30, y=y * -30, z=z))

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
