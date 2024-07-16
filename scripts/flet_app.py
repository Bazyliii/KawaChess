import flet
from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from flet import (
    AppBar,
    Column,
    Container,
    ControlEvent,
    CrossAxisAlignment,
    IconButton,
    Image,
    MainAxisAlignment,
    Page,
    Row,
    Text,
    TextButton,
    WindowDragArea,
    alignment,
    app,
    colors,
    icons,
)


class Logger:
    def __init__(self, width: int) -> None:
        self.__log_container = flet.ListView(
            width=width,
            auto_scroll=True,
            spacing=1,
            on_scroll_interval=0,
            divider_thickness=1,
        )

    def error(self, name: str, text: str | Exception) -> None:
        self.__log_container.controls.append(
            Text(spans=[flet.TextSpan(name + " ", flet.TextStyle(weight=flet.FontWeight.BOLD)), flet.TextSpan(str(text))], color=colors.RED_400)
        )
        self.__log_container.update()

    def warning(self, name: str, text: str) -> None:
        self.__log_container.controls.append(
            Text(spans=[flet.TextSpan(name + " ", flet.TextStyle(weight=flet.FontWeight.BOLD)), flet.TextSpan(text)], color=colors.ORANGE_400),
        )
        self.__log_container.update()

    def info(self, name: str, text: str) -> None:
        self.__log_container.controls.append(
            Text(spans=[flet.TextSpan(name + " ", flet.TextStyle(weight=flet.FontWeight.BOLD)), flet.TextSpan(text)], color=colors.GREY),
        )
        self.__log_container.update()

    def message(self, name: str, text: str) -> None:
        self.__log_container.controls.append(
            Text(spans=[flet.TextSpan(name + " ", flet.TextStyle(weight=flet.FontWeight.BOLD)), flet.TextSpan(text)], color=colors.GREEN_400),
        )
        self.__log_container.update()

    def get_logs(self) -> flet.ListView:
        return self.__log_container


class ChessApp:
    def __init__(self, page: Page) -> None:
        self.__game_status: bool = False
        self.__board_height: int = 500
        self.__board_width: int = 500
        self.__app_padding: int = 20
        self.__page: Page = page
        self.__page.title = "ChessApp Kawasaki"
        self.logger = Logger(self.__board_width * 2)
        self.__page.window.alignment = alignment.center
        self.__chess_board_svg: Image = Image(src=svg.board(), width=self.__board_width, height=self.__board_height)
        self.__page.window.title_bar_hidden = True
        self.__appbar = AppBar(
            toolbar_height=50,
            title=WindowDragArea(
                Row(
                    [
                        Text(self.__page.title, color="white"),
                    ],
                ),
                expand=True,
                maximizable=False,
            ),
            bgcolor=colors.GREY_900,
            title_spacing=self.__app_padding,
            actions=[
                IconButton(
                    icons.MINIMIZE,
                    on_click=self.minimize_app,
                    icon_size=15,
                    hover_color=colors.GREEN_400,
                    style=flet.ButtonStyle(shape=flet.RoundedRectangleBorder(radius=5)),
                ),
                IconButton(
                    icons.CHECK_BOX_OUTLINE_BLANK,
                    on_click=self.maximize_app,
                    icon_size=15,
                    selected=False,
                    selected_icon=icons.COPY_OUTLINED,
                    hover_color=colors.BLUE_400,
                    style=flet.ButtonStyle(shape=flet.RoundedRectangleBorder(radius=5)),
                ),
                IconButton(
                    icons.CLOSE_SHARP,
                    on_click=self.close_app,
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
                                        TextButton("Start", on_click=self.start_game, icon=icons.PLAY_ARROW),
                                        TextButton("Stop", on_click=self.stop_game, icon=icons.STOP_SHARP),
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
                        self.logger.get_logs(),
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

    def start_game(self, e: ControlEvent) -> None:
        try:
            self.logger.warning("[GAME STATUS]", "Game started!")
            self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
            self.__game_status = True
            self.__board = Board()
            self.__chess_board_svg.src = svg.board(self.__board)
            while self.__game_status and not self.__board.is_game_over():
                engine_move: Move | None = self.__engine.play(self.__board, Limit(time=0.1)).move
                if engine_move is None or engine_move not in self.__board.legal_moves:
                    self.logger.error("[EXCEPTION]", "NO MOVE FOUND!")
                    continue
                from_square: int = engine_move.from_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
                to_square: int = engine_move.to_square  # <- Numeric notation (0 in bottom-left corner, 63 in top-right corner)
                self.__board.push(engine_move)
                self.__chess_board_svg.src = svg.board(self.__board)
                self.logger.info("[MOVE]", "From: " + str(from_square) + " To: " + str(to_square))
                self.__page.update()
            self.__engine.close()
            self.__game_status = False
        except Exception as exception:
            self.logger.error("[EXCEPTION]", exception)
            self.stop_game(e)

    def stop_game(self, e: ControlEvent) -> None:
        self.__game_status = False
        if hasattr(self, "__engine"):
            self.__engine.close()
        self.logger.warning("[GAME STATUS]", "Game stopped!")
        self.__page.update()

    def close_app(self, e: ControlEvent) -> None:
        self.stop_game(e)
        self.__page.window.close()

    def minimize_app(self, e: ControlEvent) -> None:
        self.__page.window.minimized = True
        self.__page.update()

    def maximize_app(self, e: ControlEvent) -> None:
        if self.__page.window.maximized:
            self.__page.window.maximized = e.control.selected = False
        else:
            self.__page.window.maximized = e.control.selected = True
        self.__page.update()


if __name__ == "__main__":
    app(target=ChessApp)
