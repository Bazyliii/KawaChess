from __future__ import annotations

import zipfile
from datetime import datetime, timedelta
from os.path import exists
from sqlite3 import Connection, Cursor, connect
from typing import TYPE_CHECKING, Literal

import chess
import requests
from chess import Move
from chess.engine import Limit, SimpleEngine
from chess.pgn import Game
from cpuinfo import get_cpu_info
from pytz import timezone

if TYPE_CHECKING:
	from chess import Color, Square
	from pytz.tzinfo import BaseTzInfo

STOCKFISH_URL_AVX2: str = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip"
STOCKFISH_URL_POPCNT: str = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-sse41-popcnt.zip"
PLAYER: bool = False
TIMEZONE: BaseTzInfo = timezone("Europe/Warsaw")


class ChessApp:
	def __init__(self) -> None:
		pass


class KawasakiRobot:
	def __init__(self, ip: str) -> None:
		self.ip: str = ip

	def move_to_square(self, square: Square | int) -> None:
		pass

	def kingside_castle(self) -> None:
		pass

	def queenside_castle(self) -> None:
		pass

	def take_piece(self, square: Square | int) -> None:
		pass


class Gripper:
	def __init__(self) -> None:
		pass

	def open(self) -> None:
		pass

	def close(self) -> None:
		pass


class ChessClock:
	def __init__(self) -> None:
		pass

	def start(self) -> None:
		pass

	def stop(self) -> None:
		pass


class Board(chess.Board):
	def is_piece_on_square(self, square: Square) -> bool:
		"""
		Check if there is a piece on the specified square.

		Args:
			square (chess.Square): The square to check.

		Returns:
			bool: True if there is a piece on the square, False otherwise.
		"""
		return self.piece_at(square) is not None

	def bool(self) -> list[list[bool]]:
		"""
		A function that converts the board representation to a boolean matrix.

		Returns:
			list[list[bool]]: A matrix of boolean values representing the board.
		"""
		return [[sq != "." for sq in row.split(" ")] for row in str(self).split("\n")]


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
			self.connection: Connection = connect(self.name)
			self.cursor: Cursor = self.connection.cursor()

	def __del__(self) -> None:
		self.connection.close()

	def add_game_data(self, board: Board, start_datetime: datetime, players: tuple[str, ...] = ("Stockfish", "Stockfish")) -> None:
		game: Game = Game().from_board(board)
		duration: timedelta = datetime.now(TIMEZONE) - start_datetime
		result_id: Literal[1, 2, 3, 4, 5, 6, 7, 8] = 1
		match game.headers["Result"]:
			case "1-0":
				result_id = 2
			case "0-1":
				result_id = 3
			case "1/2-1/2":
				if board.is_fivefold_repetition():
					result_id = 4
				elif board.is_stalemate():
					result_id = 5
				elif board.is_fifty_moves():
					result_id = 6
				elif board.is_insufficient_material():
					result_id = 7
				else:
					result_id = 8  # FIXME <- This may be resignation. Handle it later.
			case _:
				raise ResultError(result_id)
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
				result_id,
				board.fullmove_number,
				board.fen(),
				str(game.mainline_moves()),
			),
		)
		self.connection.commit()


class MoveError(Exception):
	def __init__(self, move: Move | None = None, message: str = "Move value is None or illegal! Move: ") -> None:
		"""Common base class for all chess Move errors."""
		self.move: Move | None = move
		self.message: str = message
		super().__init__(self.message, self.move)


class ResultError(Exception):
	def __init__(self, result: Literal[1, 2, 3, 4, 5, 6, 7, 8] = 1, message: str = "Result value is not within legal range! Result: ") -> None:
		"""Common base class for all Result errors."""
		self.result: Literal[1, 2, 3, 4, 5, 6, 7, 8] = result
		self.message: str = message
		super().__init__(self.message, self.result)


def get_engine() -> SimpleEngine:
	if "avx2" in get_cpu_info()["flags"]:
		engine_path = r"stockfish\stockfish-windows-x86-64-avx2.exe"
		avx = True
	else:
		engine_path = r"stockfish\stockfish-windows-x86-64-sse41-popcnt.exe"
		avx = False

	if not exists(engine_path):
		zip_file: Literal["POPCNT.zip", "AVX2.zip"] = "AVX2.zip" if avx else "POPCNT.zip"
		with open(zip_file, "wb") as f:
			f.write(requests.get(STOCKFISH_URL_AVX2 if avx else STOCKFISH_URL_POPCNT, timeout=30).content)
		with zipfile.ZipFile(zip_file, "r") as zip_ref:
			zip_ref.extractall()
	return SimpleEngine.popen_uci(engine_path)


def get_user_move() -> Move | None:
	return Move.from_uci(input("Your move: "))


def chess_game() -> None:
	players: tuple[str, ...] = ("Stockfish", "Human")
	engine: SimpleEngine = get_engine()
	database: ChessDatabase = ChessDatabase("chess.db")
	board: Board = Board()
	start_datetime: datetime = datetime.now(TIMEZONE)
	while not board.is_game_over():
		engine_move: Move | None = engine.play(board, Limit(time=0.0001)).move
		if engine_move is None or engine_move not in board.legal_moves:
			raise MoveError(engine_move)  # <- No move found error / maybe will be handled in the future
		from_square: int = engine_move.from_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
		to_square: int = engine_move.to_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
		now_moving: Color = board.turn  # <- Color (True for white, False for black)
		castling: Literal[0, 1, 2] = 0  # <- Castling type (0 for no castling, 1 for kingside, 2 for queenside)
		if board.is_castling(engine_move):
			castling = 1 if board.is_kingside_castling(engine_move) else 2
		board.push(engine_move)
		if PLAYER:
			user_move: Move | None = get_user_move()
			if user_move is None or user_move not in board.legal_moves:
				raise MoveError(user_move)  # <- No move found error / maybe will be handled in the future
			board.push(user_move)
	engine.quit()
	database.add_game_data(board, start_datetime, players)


if __name__ == "__main__":
	chess_game()
