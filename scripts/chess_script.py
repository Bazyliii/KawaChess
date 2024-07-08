import zipfile
from datetime import date, datetime
from os.path import exists
from time import sleep
from typing import Literal

import chess
import requests
from chess import Color, Move
from chess.engine import Limit, PlayResult, SimpleEngine
from chess.pgn import Game
from cpufeature import CPUFeature


class Board(chess.Board):
    def is_piece_on_square(self, square: chess.Square) -> bool:
        """
        Check if there is a piece on the specified square.

        Args:
            square (chess.Square): The square to check.

        Returns:
            bool: True if there is a piece on the square, False otherwise.
        """
        return board.piece_at(square) is not None

    def bool(self) -> list[list[bool]]:
        """
        A function that converts the board representation to a boolean matrix.

        Returns:
            list[list[bool]]: A matrix of boolean values representing the board.
        """
        return [[True if sq != "." else False for sq in row.split(" ")] for row in str(board).split("\n")]


STOCKFISH_URL_AVX2: str = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip"
STOCKFISH_URL_POPCNT: str = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-sse41-popcnt.zip"

if CPUFeature.get("OS_AVX2") or CPUFeature.get("AVX2"):
    engine_path = r"stockfish\stockfish-windows-x86-64-avx2.exe"
else:
    engine_path = r"stockfish\stockfish-windows-x86-64-sse41-popcnt.exe"

if not exists(engine_path):
    zip_file: Literal["POPCNT.zip"] | Literal["AVX2.zip"] = "POPCNT.zip" if not CPUFeature.get("OS_AVX2") or not CPUFeature.get("AVX2") else "AVX2.zip"
    with open(zip_file, "wb") as f:
        f.write(requests.get(STOCKFISH_URL_AVX2 if zip_file == "AVX2.zip" else STOCKFISH_URL_POPCNT).content)
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall()

engine: SimpleEngine = SimpleEngine.popen_uci(engine_path)


board: Board = Board()
while not board.is_game_over():
    engine_move: Move | None = engine.play(board, Limit(time=0.1)).move
    if engine_move is None:
        raise Exception("ERROR NO MOVE FOUND")  # <- No move found error / maybe will be handled in the future

    from_square: int = engine_move.from_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
    to_square: int = engine_move.to_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
    now_moving: Color = board.turn  # <- Color (True for white, False for black)
    castling: Literal[0, 1, 2] = 0  # <- Castling type (0 for no castling, 1 for kingside, 2 for queenside)
    if board.is_castling(engine_move):
        castling: Literal[0, 1, 2] = 1 if board.is_kingside_castling(engine_move) else 2
    print(
        f"{from_square} -> {to_square}, Castling: {'None' if castling == 0 else 'Kingside' if castling == 1 else 'Queenside'}, Now moving: {'White' if now_moving else 'Black'}"
    )  # noqa: E501
    board.push(engine_move)
    print(board)

game: Game = Game().from_board(board)
game.headers["White"] = "Stockfish"
game.headers["Black"] = "Stockfish"
game.headers["Time"] = datetime.now().strftime("%H:%M:%S")
game.headers["Date"] = datetime.now().strftime("%d.%m.%Y")
print(game)  # PGN zapis rozgrywki
print(board.fen())  # Pozycja końcowa w formacie FEN
engine.quit()
