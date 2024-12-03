from datetime import datetime, timedelta
from os.path import exists
from sqlite3 import Connection, Cursor, connect
from typing import Literal

from chess import Board
from chess.pgn import Game


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


class ChessEngine:
    pass


class ChessGame:
    pass
