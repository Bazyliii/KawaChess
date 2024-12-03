from datetime import datetime, timedelta
from os.path import exists
from sqlite3 import Connection, Cursor, connect
from typing import Literal

from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from chess.pgn import Game
from flet import (
    AppBar,
    BorderSide,
    ButtonStyle,
    ClipBehavior,
    Column,
    Container,
    ControlEvent,
    CrossAxisAlignment,
    DataCell,
    DataColumn,
    DataRow,
    DataTable,
    Divider,
    ElevatedButton,
    FontWeight,
    Icon,
    IconButton,
    Image,
    ListView,
    MainAxisAlignment,
    Markdown,
    NavigationRail,
    NavigationRailDestination,
    NavigationRailLabelType,
    Page,
    RoundedRectangleBorder,
    Row,
    ScrollMode,
    Slider,
    Tab,
    TabAlignment,
    Tabs,
    Text,
    TextAlign,
    TextButton,
    TextField,
    TextOverflow,
    TextSpan,
    TextStyle,
    VerticalDivider,
    WindowDragArea,
    alignment,
    app,
    border,
    border_radius,
    icons,
    padding,
)

from kawachess import colors, flet_components


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
                );""",
                """
                INSERT INTO results(name)
                    VALUES  ("NO RESULT"),
                            ("WHITE WON"),
                            ("BLACK WON"),
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
            self.connection: Connection = connect(self.name, check_same_thread=False)
            self.cursor: Cursor = self.connection.cursor()

    def add_game_data(
        self,
        board: Board,
        start_datetime: datetime,
        duration: timedelta,
        stockfish_skill_level: int,
        players: tuple[str, ...] = ("Stockfish", "Player"),
    ) -> None:
        game: Game = Game().from_board(board)
        self.cursor.execute(
            """
            INSERT INTO chess_games(white_player, black_player, date, game_duration, result_id,stockfish_skill_level ,move_count, FEN_end_position, PGN_game_sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,  # noqa: E501
            (
                players[0],
                players[1],
                start_datetime.strftime("%d-%m-%Y %H:%M:%S"),
                str(duration - timedelta(seconds=1)),
                self.get_game_results(board),
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

    def get_game_data(self) -> list[tuple]:
        self.cursor.execute(
            """
            SELECT chess_games.*, results.name
            FROM chess_games
            JOIN results ON chess_games.result_id = results.id
            """,
        )
        return self.cursor.fetchall()


class GameContainer(Column):
    def __init__(self, board_size: int, skill_level: int = 20) -> None:
        super().__init__()
        self.skill_level: int = skill_level
        self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
        self.__engine.configure({"Threads": "2", "Hash": "512", "Skill Level": self.skill_level})
        self.__game_status: bool = False
        self.pending_game_stockfish_skill_lvl: int
        self.__board_colors: dict[str, str] = {
            "square light": "#DDDDDD",
            "square dark": colors.ACCENT_COLOR_1,
            "margin": colors.ACCENT_COLOR_2,
            "coord": colors.WHITE,
            "square light lastmove": colors.ACCENT_COLOR_4,
            "square dark lastmove": colors.ACCENT_COLOR_3,
        }
        self.__chess_board_svg: Image = Image(svg.board(Board(), colors=self.__board_colors), width=board_size, height=board_size)
        self.player_name: str = "Player"
        self.expand = True
        self.bgcolor = colors.ACCENT_COLOR_1
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.visible = True
        self.spacing = 50
        self.controls = [
            Row(
                [
                    self.__chess_board_svg,
                    Image(src="logo.png", width=390, height=390),
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
            Row(
                [
                    flet_components.Button(
                        text="Start game",
                        on_click=lambda _: self.start_game(),
                        icon=icons.PLAY_ARROW_OUTLINED,
                    ),
                    flet_components.Button(
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
        self.__game_status = True
        self.pending_game_stockfish_skill_lvl = self.skill_level
        board: Board = Board()
        while self.__game_status and not board.is_game_over():
            engine_move: Move | None = self.__engine.play(board, Limit(time=1.0)).move
            if engine_move is None or engine_move not in board.legal_moves:
                continue
            if self.__game_status:
                board.push(engine_move)
                self.__chess_board_svg.src = svg.board(board, colors=self.__board_colors, lastmove=engine_move)
                self.update()
        self.resign_game()
        if board.is_game_over():
            print(board.result())

    def resign_game(self) -> None:
        if not self.__game_status:
            return
        self.__game_status = False
        self.update()

    def close(self) -> None:
        self.__game_status = False
        self.__engine.quit()
