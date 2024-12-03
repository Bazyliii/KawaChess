from kawachess import ChessGame, ChessDatabase


database = ChessDatabase("chess.db")


game = ChessGame(database)

game.start_game()