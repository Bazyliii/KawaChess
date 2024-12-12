from base64 import b64encode
from collections.abc import Callable
from datetime import datetime, timedelta
from os.path import exists
from sqlite3 import Connection, Cursor, connect
from time import sleep
from typing import TYPE_CHECKING, Final

from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from chess.pgn import Game
from cv2 import CAP_PROP_FPS, VideoCapture, imencode, resize
from flet import Column, CrossAxisAlignment, FilterQuality, Image, MainAxisAlignment, Row, icons
from pytz import BaseTzInfo, timezone

from kawachess.colors import ACCENT_COLOR_1, ACCENT_COLOR_2, ACCENT_COLOR_3, ACCENT_COLOR_4, BLUE, GREEN, GREY, MAIN_COLOR, RED, WHITE
from kawachess.flet_components import Button
from kawachess.robot import RobotConnection

if TYPE_CHECKING:
    from numpy import ndarray

TIMEZONE: Final[BaseTzInfo] = timezone("Europe/Warsaw")


class ChessDatabase:
    def __init__(self, name: str) -> None:
        self.name: str = name
        if not exists(self.name):
            self.connection: Connection = connect(self.name)
            self.cursor: Cursor = self.connection.cursor()
            for query in (
                """
                CREATE TABLE IF NOT EXISTS results(
                    id INTEGER,
                    name TEXT NOT NULL,
                    CONSTRAINT results_pk PRIMARY KEY (id)
                );
                """,
                """
                INSERT INTO results(name)
                    VALUES  ("NO RESULT"),
                            ("WHITE WON"),
                            ("BLACK WON"),
                            ("DRAW BY FIVEFOLD REPETITION"),
                            ("DRAW BY STALEMATE"),
                            ("DRAW BY FIFTY-MOVE RULE"),
                            ("DRAW BY INSUFFICIENT MATERIAL"),
                            ("DRAW"),
                            ("PLAYER RESIGNED");
                """,
                """
                CREATE TABLE IF NOT EXISTS chess_games(
                    id INTEGER NOT NULL,
                    white_player TEXT NOT NULL,
                    black_player TEXT NOT NULL,
                    date TEXT NOT NULL,
                    game_duration TEXT NOT NULL,
                    result_id INTEGER NOT NULL,
                    stockfish_skill_level INTEGER NOT NULL,
                    move_count INTEGER NOT NULL,
                    FEN_end_position TEXT NOT NULL,
                    PGN_game_sequence TEXT NOT NULL,
                    CONSTRAINT chess_games_pk PRIMARY KEY (id)
                    CONSTRAINT results_fk FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE CASCADE ON UPDATE CASCADE
                );
                """,
            ):
                self.cursor.execute(query)
            self.connection.commit()
        else:
            self.connection: Connection = connect(self.name)
            self.cursor: Cursor = self.connection.cursor()

    def add_game_data(
        self,
        game: Game,
        start_datetime: datetime,
        duration: timedelta,
        stockfish_skill_level: int,
        players: tuple[str, str] = ("Stockfish", "Player"),
    ) -> None:
        board: Board = game.board()
        self.cursor.execute(
            """
            INSERT INTO chess_games(white_player, black_player, date, game_duration, result_id,stockfish_skill_level ,move_count, FEN_end_position, PGN_game_sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,  # noqa: E501
            (
                players[0],
                players[1],
                start_datetime.strftime("%d-%m-%Y %H:%M:%S"),
                str(duration).split(".")[0],
                self.get_game_results(game),
                stockfish_skill_level,
                board.fullmove_number,
                board.fen(),
                str(game.mainline_moves()),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        if self.connection:
            self.connection.close()

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self.close()

    def __enter__(self) -> "ChessDatabase":
        return self

    @staticmethod
    def get_game_results(game: Game) -> int:
        game_board: Board = game.board()

        result: dict[int, bool] = {
            9: "resigned" in game.headers["Result"],
            2: "1-0" in game.headers["Result"],
            3: "0-1" in game.headers["Result"],
            4: "1/2-1/2" in game.headers["Result"] and game_board.is_fivefold_repetition(),
            5: "1/2-1/2" in game.headers["Result"] and game_board.is_stalemate(),
            6: "1/2-1/2" in game.headers["Result"] and game_board.is_fifty_moves(),
            7: "1/2-1/2" in game.headers["Result"] and game_board.is_insufficient_material(),
            8: "1/2-1/2" in game.headers["Result"]
            and not game_board.is_fivefold_repetition()
            and not game_board.is_stalemate()
            and not game_board.is_fifty_moves()
            and not game_board.is_insufficient_material(),
        }

        return next((key for key, value in result.items() if value), 1)

    def get_game_data(self) -> list[tuple]:
        self.cursor.execute(
            """
            SELECT chess_games.*, results.name
            FROM chess_games
            JOIN results ON chess_games.result_id = results.id
            """,
        )
        return self.cursor.fetchall()


class OpenCVDetection(Image):
    def __init__(self, image_size: int) -> None:
        super().__init__()
        self.capture = VideoCapture(0)
        self.image_size: int = image_size
        self.width = self.height = self.image_size
        self.filter_quality = FilterQuality.NONE

    def did_mount(self) -> None:
        if not self.capture.isOpened() or self.capture.get(CAP_PROP_FPS) == 0:
            self.src = "no_camera.png"
            self.update()
            return
        frame: ndarray = self.capture.read()[1]
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
            frame: ndarray = self.capture.read()[1]
            resized_frame: ndarray = resize(frame[top:bottom, left:right], (self.image_size, self.image_size))
            self.src_base64 = b64encode(imencode(".bmp", resized_frame)[1]).decode("utf-8")
            self.update()
            sleep(delay)

    def build(self) -> None:
        self.img = Image(height=self.image_size, width=self.image_size)

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        self.capture.release()


class GameContainer(Column):
    def __init__(self, board_size: int, dialog: Callable[[str], None], robot: RobotConnection, skill_level: int = 20) -> None:
        super().__init__()
        self.dialog: Callable[[str], None] = dialog
        self.robot: RobotConnection = robot
        self.skill_level: int = skill_level
        self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
        self.__engine.configure({"Threads": "2", "Hash": "512", "Skill Level": self.skill_level})
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
        self.player_name: str = "Player"
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
        self.__start_datetime = datetime.now(TIMEZONE)
        self.__game_status = True
        self.__pending_game_stockfish_skill_lvl = self.skill_level
        while self.__game_status and not self.board.is_game_over():
            engine_move: Move | None = self.__engine.play(self.board, Limit(time=1.0)).move
            if engine_move is None or engine_move not in self.board.legal_moves:
                continue
            if self.__game_status:
                self.board.push(engine_move)
                self.__chess_board_svg.src = svg.board(self.board, colors=self.__board_colors, lastmove=engine_move)
                self.update()
        if self.board.is_game_over():
            self.end_game()

    def add_game_data_to_db(self, game: Game) -> None:
        with ChessDatabase("chess.db") as database:
            database.add_game_data(
                game,
                self.__start_datetime,
                datetime.now(TIMEZONE) - self.__start_datetime,
                self.__pending_game_stockfish_skill_lvl,
                ("Stockfish", self.player_name),
            )
        self.board = Board()
        self.__game_status = False
        self.update()

    def end_game(self) -> None:
        if not self.__game_status:
            return
        game: Game = Game().from_board(self.board)
        self.dialog(game.headers["Result"])
        self.add_game_data_to_db(game)

    def resign_game(self) -> None:
        if not self.__game_status:
            return
        game: Game = Game().from_board(self.board)
        game.headers["Result"] = "resigned"
        self.dialog("Player resigned!")
        self.add_game_data_to_db(game)

    def close(self) -> None:
        if self.__game_status:
            self.add_game_data_to_db(Game().from_board(self.board))
        self.__opencv_detection.close()
        self.__engine.quit()

    def set_player_name(self, player_name: str) -> None:
        self.player_name = player_name
