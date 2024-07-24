from datetime import datetime, timedelta
from enum import Enum
from os.path import exists
from sqlite3 import Connection, Cursor, connect
from typing import Literal

import flet
from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from chess.pgn import Game
from flet import (
    AppBar,
    Column,
    Container,
    ControlEvent,
    CrossAxisAlignment,
    FontWeight,
    IconButton,
    Image,
    MainAxisAlignment,
    Page,
    Row,
    Text,
    TextButton,
    TextSpan,
    TextStyle,
    WindowDragArea,
    alignment,
    app,
    colors,
    icons,
)
from pytz import timezone
from pytz.tzinfo import BaseTzInfo

TIMEZONE: BaseTzInfo = timezone("Europe/Warsaw")


class MessageType(Enum):
    ERROR = ("[ERROR] ", colors.RED_400)
    WARNING = ("[WARNING] ", colors.ORANGE_400)
    INFO = ("[INFO] ", colors.GREEN_400)
    EXCEPTION = ("[EXCEPTION] ", colors.RED_400)
    GAME_STATUS = ("[GAME STATUS] ", colors.YELLOW_600)
    MOVE = ("[MOVE] ", colors.GREEN_400)


class Logger:
    def __init__(self, width: int) -> None:
        self.__log_container = flet.ListView(
            width=width,
            clip_behavior=flet.ClipBehavior.ANTI_ALIAS,
            auto_scroll=True,
            spacing=1,
            on_scroll_interval=0,
            divider_thickness=1,
        )

    def __call__(self, msg_type: MessageType, text: str | Exception) -> None:
        self.__log_container.controls.append(
            Text(
                spans=[
                    TextSpan(datetime.now(TIMEZONE).strftime("%H:%M:%S "), TextStyle(color=colors.WHITE38)),
                    TextSpan(msg_type.value[0], TextStyle(weight=FontWeight.BOLD)),
                    TextSpan(str(text)),
                ],
                color=msg_type.value[1],
            ),
        )
        self.__log_container.update()

    def clear(self, e: ControlEvent) -> None:  # noqa: ARG002
        self.__log_container.controls = []
        self(MessageType.WARNING, "Log cleared!")

    @property
    def log_container(self) -> flet.ListView:
        return self.__log_container


class ChessDatabase:
    def __init__(self, name: str) -> None:
        self.name: str = name
        if not exists(self.name):
            self.connection: Connection = connect(self.name, check_same_thread=False)
            self.cursor: Cursor = self.connection.cursor()
            for query in (
                """
                CREATE TABLE IF NOT EXISTS results(
                    id INTEGER,
                    name TEXT NOT NULL,
                    CONSTRAINT results_pk PRIMARY KEY (id)
                );""",
                """
                INSERT INTO results(name)
                    VALUES  ("NO RESULT"),
                            ("WHITE WIN"),
                            ("BLACK WIN"),
                            ("DRAW BY FIVEFOLD REPETITION"),
                            ("DRAW BY STALEMATE"),
                            ("DRAW BY FIFTY-MOVE RULE"),
                            ("DRAW BY INSUFFICIENT MATERIAL"),
                            ("DRAW");
                """,
                """
                CREATE TABLE IF NOT EXISTS chess_games(
                    id INTEGER NOT NULL,
                    white_player TEXT NOT NULL,
                    black_player TEXT NOT NULL,
                    date TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    result_id INTEGER NOT NULL,
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
            self.connection: Connection = connect(self.name, check_same_thread=False)
            self.cursor: Cursor = self.connection.cursor()

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def get_game_results(board: Board) -> Literal[1, 2, 3, 4, 5, 6, 7, 8]:
        match Game().from_board(board).headers["Result"]:
            case "1-0":
                result = 2
            case "0-1":
                result = 3
            case "1/2-1/2":
                if board.is_fivefold_repetition():
                    result = 4
                if board.is_stalemate():
                    result = 5
                if board.is_fifty_moves():
                    result = 6
                if board.is_insufficient_material():
                    result = 7
                result = 8
            case _:
                result = 1
        return result

    def add_game_data(self, board: Board, start_datetime: datetime, players: tuple[str, ...] = ("Stockfish", "Stockfish")) -> None:
        game: Game = Game().from_board(board)
        duration: timedelta = datetime.now(TIMEZONE) - start_datetime
        self.cursor.execute(
            """
            INSERT INTO chess_games(white_player, black_player, date, duration, result_id, move_count, FEN_end_position, PGN_game_sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                players[0],
                players[1],
                start_datetime.strftime("%d-%m-%Y %H:%M:%S"),
                str(duration),
                self.get_game_results(board),
                board.fullmove_number,
                board.fen(),
                str(game.mainline_moves()),
            ),
        )
        self.connection.commit()


class ChessApp:
    def __init__(self, page: Page) -> None:
        self.__game_status: bool = False
        self.__board_height: int = 500
        self.__board_width: int = 500
        self.__app_padding: int = 20
        self.__page: Page = page
        self.__page.title = "ChessApp Kawasaki"
        self.logger = Logger(self.__board_width * 2)
        self.database = ChessDatabase("chess.db")
        self.__page.window.alignment = alignment.center
        self.__maximize_button: IconButton = IconButton(
            icons.CHECK_BOX_OUTLINE_BLANK,
            on_click=lambda _: self.__maximize(),
            icon_size=15,
            selected=False,
            selected_icon=icons.COPY_OUTLINED,
            hover_color=colors.BLUE_400,
            style=flet.ButtonStyle(shape=flet.RoundedRectangleBorder(radius=5)),
        )
        self.__chess_board_svg: Image = Image(src=svg.board(Board()), width=self.__board_width, height=self.__board_height)
        self.__page.window.title_bar_hidden = True
        self.__page.window.on_event = self.__window_event
        self.__appbar = AppBar(
            toolbar_height=45,
            title=WindowDragArea(
                Row(
                    [
                        Text(self.__page.title, color="white", overflow=flet.TextOverflow.ELLIPSIS, expand=True),
                    ],
                ),
                expand=True,
                maximizable=True,
            ),
            bgcolor=colors.GREY_900,
            title_spacing=self.__app_padding,
            actions=[
                IconButton(
                    icons.MINIMIZE,
                    on_click=lambda _: self.__minimize(),
                    icon_size=15,
                    hover_color=colors.GREEN_400,
                    style=flet.ButtonStyle(shape=flet.RoundedRectangleBorder(radius=5)),
                ),
                self.__maximize_button,
                IconButton(
                    icons.CLOSE_SHARP,
                    on_click=lambda _: self.__close(),
                    icon_size=15,
                    hover_color=colors.RED_400,
                    style=flet.ButtonStyle(shape=flet.RoundedRectangleBorder(radius=5)),
                ),
                Container(width=20),
            ],
        )
        self.__layout = Column(
            [
                Row(
                    [
                        Column(
                            [
                                self.__chess_board_svg,
                                Row(
                                    [
                                        TextButton("Start", on_click=lambda _: self.start_game(), icon=icons.PLAY_ARROW),
                                        TextButton("Stop", on_click=lambda _: self.stop_game(), icon=icons.STOP_SHARP),
                                        TextButton("Clear logs", on_click=self.logger.clear, icon=icons.CLEAR_ALL),
                                    ],
                                ),
                            ],
                            alignment=MainAxisAlignment.CENTER,
                            horizontal_alignment=CrossAxisAlignment.CENTER,
                        ),
                        Container(width=self.__app_padding),
                        Column(
                            [
                                Image(
                                    src="https://upload.wikimedia.org/wikipedia/commons/3/32/OpenCV_Logo_with_text_svg_version.svg",
                                    width=self.__board_width,
                                    height=self.__board_height,
                                ),
                            ],
                            alignment=MainAxisAlignment.CENTER,
                            horizontal_alignment=CrossAxisAlignment.CENTER,
                        ),
                    ],
                    alignment=MainAxisAlignment.CENTER,
                ),
                Row(
                    [
                        self.logger.log_container,
                    ],
                    alignment=MainAxisAlignment.CENTER,
                    vertical_alignment=CrossAxisAlignment.CENTER,
                    expand=True,
                    spacing=20,
                ),
            ],
            expand=True,
            alignment=MainAxisAlignment.CENTER,
            horizontal_alignment=CrossAxisAlignment.CENTER,
        )
        self.__page.add(self.__appbar)
        self.__page.add(self.__layout)
        self.__page.update()

    def start_game(self) -> None:
        if self.__game_status:
            return
        start_datetime: datetime = datetime.now(TIMEZONE)
        self.logger(MessageType.GAME_STATUS, "Game started!")
        self.__game_status = True
        self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
        self.__board = Board()
        self.__chess_board_svg.src = svg.board(self.__board)
        while self.__game_status and not self.__board.is_game_over():
            engine_move: Move | None = self.__engine.play(self.__board, Limit(time=0.01)).move
            if engine_move is None or engine_move not in self.__board.legal_moves:
                self.logger(MessageType.ERROR, "No move found!")
                continue
            from_square: int = engine_move.from_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
            to_square: int = engine_move.to_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
            if self.__game_status:
                self.__board.push(engine_move)
                self.__chess_board_svg.src = svg.board(self.__board)
                self.__page.update()
                self.logger(MessageType.MOVE, f"Engine: {engine_move.uci()}")
        self.stop_game()
        if self.__board.is_game_over():
            self.database.add_game_data(self.__board, start_datetime, ("Stockfish", "Human"))
            self.logger(MessageType.INFO, "Game data saved to database!")

    def stop_game(self) -> None:  
        if not self.__game_status:
            return
        self.__game_status = False
        self.__engine.quit()
        self.logger(MessageType.GAME_STATUS, "Game stopped!")
        self.__page.update()

    def __close(self) -> None:
        self.stop_game()
        self.database.close()
        self.__page.window.close()

    def __minimize(self) -> None:
        self.__page.window.minimized = True
        self.__page.update()

    def __maximize(self) -> None:
        self.__page.window.maximized = not self.__page.window.maximized
        self.__page.update()

    def __window_event(self, e: ControlEvent) -> None:
        if e.data in {"unmaximize", "maximize"}:
            self.__maximize_button.selected = self.__page.window.maximized
            self.__page.update()


if __name__ == "__main__":
    app(target=ChessApp)
