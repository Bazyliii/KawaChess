from collections.abc import Callable
from datetime import datetime
from enum import Enum, auto
from typing import Final

from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from flet import Column, CrossAxisAlignment, Image, MainAxisAlignment, Row, icons
from pytz import BaseTzInfo, timezone

from kawachess.colors import ACCENT_COLOR_1, ACCENT_COLOR_2, ACCENT_COLOR_3, ACCENT_COLOR_4, WHITE
from kawachess.components import Button
from kawachess.database import ChessDatabase, GameData
from kawachess.robot import Cartesian, Command, Connection, Point
from kawachess.vision import OpenCVDetection

TIMEZONE: Final[BaseTzInfo] = timezone("Europe/Warsaw")


class Castling(Enum):
    Kingside = auto()
    Queenside = auto()


class GameContainer(Column):
    def __init__(self, board_size: int, dialog: Callable[[str], None], robot: Connection) -> None:
        super().__init__()
        self.base_point: Point = Point("A1", Cartesian(91.362, 554.329, -193.894, -137.238, 179.217, -5.03))
        self.dialog: Callable[[str], None] = dialog
        self.robot: Connection = robot
        self.robot.send(Command.ADD_POINT, self.base_point)
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
                        icon=icons.PLAY_ARROW_OUTLINED,
                    ),
                    Button(
                        text="Resign game",
                        on_click=lambda _: self.resign_game(),
                        icon=icons.HANDSHAKE_OUTLINED,
                    ),
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
        ]

    def start_game(self) -> None:
        if self.__game_status:
            return
        player_turn: bool = False
        self.__engine.configure({"Skill Level": self.__skill_level})
        self.__start_datetime = datetime.now(TIMEZONE)
        self.__game_status = True
        self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors)
        self.update()
        self.__pending_game_stockfish_skill_lvl = self.__skill_level
        while self.__game_status and not self.board.is_game_over():
            engine_move: Move | None = self.__engine.play(self.board, Limit(time=1.0)).move
            if engine_move is None or engine_move not in self.board.legal_moves:
                continue
            if self.__game_status:
                from_point: Point = self.calculate_point_to_move(engine_move.uci()[:2])
                to_point: Point = self.calculate_point_to_move(engine_move.uci()[2:])
                print(from_point, to_point)
                self.robot.send(Command.ADD_POINT, from_point)
                self.robot.send(Command.ADD_POINT, to_point)

                program: str = f"""HMOVE {from_point.name}\nHMOVE {to_point.name}"""
                print(program)
                self.robot.write_program(program, "temp_game")
                self.robot.send(Command.EXECUTE_PROG, "temp_game")
                self.board.push(engine_move)
                self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=engine_move)
                self.update()
                player_turn = True
                self.dialog("Player move")
                while player_turn and self.__game_status:
                    try:
                        player_move: Move = Move.from_uci(input("Enter move: "))
                    except:
                        self.dialog("Invalid move")
                        continue
                    if player_move in self.board.legal_moves:
                        self.board.push(player_move)
                        self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=player_move)
                        self.update()
                        player_turn = False
                    else:
                        self.dialog("Invalid move")
        if self.board.is_game_over():
            self.end_game()

    def add_data_to_db(self, board: Board) -> None:
        game_data = GameData(board, self.__pending_game_stockfish_skill_lvl, self.__start_datetime, datetime.now(TIMEZONE), ("Stockfish", self.__player_name))
        with ChessDatabase("chess.db") as database:
            database.add(game_data)
        self.board = Board()
        self.__game_status = False
        self.update()

    def end_game(self) -> None:
        if not self.__game_status:
            return
        self.dialog("Game over!")
        self.add_data_to_db(self.board)

    def resign_game(self) -> None:
        if not self.__game_status:
            return
        self.dialog("Player resigned!")
        self.add_data_to_db(self.board)

    def close(self) -> None:
        if self.__game_status:
            self.add_data_to_db(self.board)
            self.__game_status = False
        self.__opencv_detection.close()
        self.__engine.quit()

    def calculate_point_to_move(self, uci_move: str, z: float = 0.0) -> Point:
        x: int = ord(uci_move[0]) - ord("a")
        y: int = int(uci_move[1]) - 1
        return self.base_point.shift(uci_move, Cartesian(x=x * -40, y=y * -40, z=z))

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
