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
        self.drop_point: Point = Point("Drop", Cartesian(300.362, 448.329, -93.894, -137.238, 179.217, -5.03))
        self.dialog: Callable[[str], None] = dialog
        self.robot: Connection = robot
        self.robot.add_translation_point(self.base_point)
        self.robot.add_translation_point(self.drop_point)
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
        self.board.reset()
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
            self.process_move(engine_move)
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
        game_data = GameData(self.board, self.__pending_game_stockfish_skill_lvl, self.__start_datetime, datetime.now(TIMEZONE), ("Stockfish", self.__player_name))
        with ChessDatabase("chess.db") as database:
            database.add(game_data)
        self.__game_status = False
        if self.board.is_game_over():
            self.dialog("Game over!")
        self.update()

    def resign_game(self) -> None:
        if not self.__game_status:
            return
        self.__game_status = False
        self.dialog("Player resigned!")

    def close(self) -> None:
        if self.__game_status:
            self.__game_status = False
        self.__opencv_detection.close()
        self.__engine.quit()

    def calculate_point_to_move(self, uci_move: str, z: float = 0.0) -> Point:
        x: int = ord(uci_move[0]) - ord("a")
        y: int = int(uci_move[1]) - 1
        return self.base_point.shift(uci_move, Cartesian(x=x * -30, y=y * -30, z=z))

    def process_move(self, move: Move) -> None:
        from_point: Point = self.calculate_point_to_move(move.uci()[:2], z=80)
        to_point: Point = self.calculate_point_to_move(move.uci()[2:], z=80)

        self.robot.add_translation_point(from_point)
        self.robot.add_translation_point(to_point)

        program: str | None = None
        name: str | None = None
        if self.board.is_capture(move):
            name = "move_with_capture"
            program = f"""
                    SPEED 5 ALWAYS
                    LMOVE {to_point.name}
                    LDEPART -80
                    LDEPART 80
                    LMOVE {self.drop_point.name}
                    LDEPART -80
                    LDEPART 80
                    LMOVE {from_point.name}
                    LDEPART -80
                    LDEPART 80
                    LMOVE {to_point.name}
                    LDEPART -80
                    LDEPART 80
                    LMOVE {self.drop_point.name}
                    """
        elif self.board.is_kingside_castling(move):
            if self.board.turn:
                name = "kingside_castling_white"
                program = f"""
                        SPEED 5 ALWAYS
                        LMOVE {self.drop_point.name}
                        """
            else:
                name = "kingside_castling_black"
                program = f"""
                        SPEED 5 ALWAYS
                        LMOVE {self.drop_point.name}
                        """
        elif self.board.is_queenside_castling(move):
            if self.board.turn:
                name = "queenside_castling_white"
                program = f"""
                        SPEED 5 ALWAYS
                        LMOVE {self.drop_point.name}
                        """
            else:
                name = "queenside_castling_black"
                program = f"""
                        SPEED 5 ALWAYS
                        LMOVE {self.drop_point.name}
                        """
        elif self.board.is_en_passant(move):
            name = "en_passant"
            program = f"""
                    SPEED 5 ALWAYS
                    LMOVE {self.drop_point.name}
                    """
        else:
            name = "move_without_capture"
            program = f"""
                    SPEED 5 ALWAYS
                    LMOVE {from_point.name}
                    LDEPART -80
                    LDEPART 80
                    LMOVE {to_point.name}
                    LDEPART -80
                    LDEPART 80
                    LMOVE {self.drop_point.name}
                    """
        if program is None or name is None:
            return
        # self.robot.(program, name)
        # self.robot.send(Command.EXECUTE_PROG, name)

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
