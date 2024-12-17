from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sqlite3 import Connection, Cursor, connect
from types import TracebackType

from chess import Board
from chess.pgn import Game
from flet import BorderSide, Column, DataCell, DataColumn, DataRow, DataTable, FontWeight, MainAxisAlignment, ScrollMode, Text, TextStyle

from kawachess.colors import ACCENT_COLOR_1, ACCENT_COLOR_3


@dataclass
class GameData:
    game_result: int
    start_datetime: str
    duration: str
    stockfish_skill_level: int
    players: tuple[str, str]
    moves: str
    move_count: int
    board_fen: str

    def __init__(self, board: Board, stockfish_skill_level: int, start_datetime: datetime, end_datetime: datetime, players: tuple[str, str]) -> None:
        game: Game = Game().from_board(board)
        self.stockfish_skill_level = stockfish_skill_level
        self.start_datetime = start_datetime.strftime("%d-%m-%Y %H:%M:%S")
        self.duration = str(end_datetime - start_datetime).split(".")[0]
        self.players = players
        self.moves = str(game.mainline_moves())
        self.move_count = board.fullmove_number
        self.board_fen = board.fen()
        results: dict[int, bool] = {
            2: game.headers["Result"] == "1-0",
            3: game.headers["Result"] == "0-1",
            4: board.is_fivefold_repetition(),
            5: board.is_stalemate(),
            6: board.is_fifty_moves(),
            7: board.is_insufficient_material(),
            8: not any(
                (
                    board.is_fivefold_repetition(),
                    board.is_stalemate(),
                    board.is_fifty_moves(),
                    board.is_insufficient_material(),
                ),
            ),
        }
        self.game_result = next((key for key, value in results.items() if value), 1)


class ChessDatabase:
    def __init__(self, name: str) -> None:
        self.name: str = name
        if not Path(self.name).exists():
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

    def __exit__(self, exc_type: BaseException | None, exc_value: BaseException | None, exc_traceback: TracebackType | None) -> None:  # noqa: PYI036
        if self.connection:
            self.connection.close()

    def __enter__(self) -> "ChessDatabase":
        return self

    def add(self, game_data: GameData) -> None:
        self.cursor.execute(
            """
            INSERT INTO chess_games(white_player, black_player, date, game_duration, result_id,stockfish_skill_level ,move_count, FEN_end_position, PGN_game_sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,  # noqa: E501
            (
                game_data.players[0],
                game_data.players[1],
                game_data.start_datetime,
                game_data.duration,
                game_data.game_result,
                game_data.stockfish_skill_level,
                game_data.move_count,
                game_data.board_fen,
                game_data.moves,
            ),
        )
        self.connection.commit()

    def get_game_data(self) -> list[tuple]:
        self.cursor.execute(
            """
            SELECT chess_games.*, results.name
            FROM chess_games
            JOIN results ON chess_games.result_id = results.id
            """,
        )
        return self.cursor.fetchall()


class DatabaseContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.visible = False
        self.scroll = ScrollMode.ADAPTIVE
        self.height = 10000

    def update_game_data(self) -> None:
        with ChessDatabase("chess.db") as database:
            self.controls = (
                DataTable(
                    columns=[
                        DataColumn(Text("ID"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("White Player"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Black Player"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Date"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Duration"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Stockfish Skill"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Result"), heading_row_alignment=MainAxisAlignment.CENTER),
                    ],
                    rows=[
                        DataRow(
                            cells=[
                                DataCell(Text(str(row[0]))),
                                DataCell(Text(row[1])),
                                DataCell(Text(row[2])),
                                DataCell(Text(row[3])),
                                DataCell(Text(row[4])),
                                DataCell(Text(str(row[6]))),
                                DataCell(Text(row[10])),
                            ],
                        )
                        for row in database.get_game_data()
                    ],
                    width=10000,
                    sort_column_index=0,
                    data_row_max_height=50,
                    vertical_lines=BorderSide(2, ACCENT_COLOR_1),
                    horizontal_lines=BorderSide(2, ACCENT_COLOR_1),
                    heading_row_color=ACCENT_COLOR_1,
                    heading_text_style=TextStyle(weight=FontWeight.BOLD, color=ACCENT_COLOR_3),
                ),
            )
        self.update()

