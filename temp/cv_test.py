import zipfile
from datetime import datetime, timedelta
from os.path import exists
from sqlite3 import Connection, Cursor, connect
from typing import TYPE_CHECKING, Literal

import flet
import requests
from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from chess.pgn import Game
from cpuinfo import get_cpu_info
from flet import Page, ThemeMode
from pytz import timezone
from pytz.tzinfo import BaseTzInfo

if TYPE_CHECKING:
	from chess import Color, Square


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


class ChessEngine:
	STOCKFISH_URL_AVX2: str = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip"
	STOCKFISH_URL_POPCNT: str = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-sse41-popcnt.zip"

	@staticmethod
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
				f.write(requests.get(ChessEngine.STOCKFISH_URL_AVX2 if avx else ChessEngine.STOCKFISH_URL_POPCNT, timeout=30).content)
			with zipfile.ZipFile(zip_file, "r") as zip_ref:
				zip_ref.extractall()
		return SimpleEngine.popen_uci(engine_path)


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
			self.connection: Connection = connect(self.name)
			self.cursor: Cursor = self.connection.cursor()

	# def __del__(self) -> None:
	# 	self.connection.close()

	def add_game_data(self, board: Board, start_datetime: datetime, players: tuple[str, ...] = ("Stockfish", "Stockfish")) -> None:
		game: Game = Game().from_board(board)
		duration: timedelta = datetime.now(timezone("Europe/Warsaw")) - start_datetime
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


class ChessGame:
	TIMEZONE: BaseTzInfo = timezone("Europe/Warsaw")

	def __init__(self) -> None:
		self.players: tuple[str, ...] = ("Stockfish", "Human")
		self.engine: SimpleEngine = ChessEngine.get_engine()
		self.database: ChessDatabase = ChessDatabase("chess.db")
		self.board: Board = Board()
		self.start_datetime: datetime = datetime.now(self.TIMEZONE)

	def chess_game(self) -> None:
		while not self.board.is_game_over():
			engine_move: Move | None = self.engine.play(self.board, Limit(time=0.0001)).move
			if engine_move is None or engine_move not in self.board.legal_moves:
				raise MoveError(engine_move)  # <- No move found error / maybe will be handled in the future
			from_square: int = engine_move.from_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
			to_square: int = engine_move.to_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
			now_moving: Color = self.board.turn  # <- Color (True for white, False for black)
			castling: Literal[0, 1, 2] = 0  # <- Castling type (0 for no castling, 1 for kingside, 2 for queenside)
			if self.board.is_castling(engine_move):
				castling = 1 if self.board.is_kingside_castling(engine_move) else 2
			self.board.push(engine_move)
		self.engine.quit()
		self.database.add_game_data(self.board, self.start_datetime, self.players)

class ChessApp:
	def __init__(self, page: Page) -> None:
		self.__chess_game: ChessGame = ChessGame()
		self.__page: Page = page
		self.__page.theme_mode = ThemeMode.SYSTEM
		self.__page.window.always_on_top = True
		self.__page.window.center()
		self.__page.title = "Chess App"
		self.__chess_board = flet.Image(src=svg.board(Board()))
		page_layout = flet.Row(
			[
				flet.Column(
					[
						self.__chess_board,
					],
					alignment=flet.MainAxisAlignment.CENTER,
					horizontal_alignment=flet.CrossAxisAlignment.CENTER,
				),
			],
			expand=True,
			alignment=flet.MainAxisAlignment.CENTER,
			vertical_alignment=flet.CrossAxisAlignment.CENTER,
		)
		self.__page.add(page_layout)
		self.__page.update()

	def update_board(self, board: Board) -> None:
		self.__chess_board.src = svg.board(board)
		self.__page.update()


if __name__ == "__main__":
	flet.app(target=ChessApp)
