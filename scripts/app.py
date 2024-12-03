from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
import flet
from flet import (
    AppBar,
    ButtonStyle,
    ClipBehavior,
    Column,
    Container,
    ControlEvent,
    CrossAxisAlignment,
    FontWeight,
    Icon,
    IconButton,
    Image,
    ListView,
    MainAxisAlignment,
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
    WindowDragArea,
    alignment,
    app,
    border,
    border_radius,
    colors,
    icons,
    padding,
    NavigationRail,
    NavigationRailDestination,
    NavigationRailLabelType,
    VerticalDivider,
    Markdown
)


class CloseButton(IconButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__(
            icons.CLOSE,
            icon_size=13,
            on_click=on_click,
            icon_color=colors.GREY_400,
            hover_color=colors.RED_400,
            style=ButtonStyle(shape=RoundedRectangleBorder(radius=1)),
        )


class MinimizeButton(IconButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__(
            icons.MINIMIZE,
            icon_size=13,
            on_click=on_click,
            icon_color=colors.GREY_400,
            hover_color=colors.GREEN_400,
            style=ButtonStyle(shape=RoundedRectangleBorder(radius=1)),
        )


class MaximizeButton(IconButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__(
            icons.CHECK_BOX_OUTLINE_BLANK,
            icon_size=13,
            on_click=on_click,
            icon_color=colors.GREY_400,
            selected=False,
            selected_icon=icons.COPY_OUTLINED,
            hover_color=colors.BLUE_400,
            style=ButtonStyle(shape=RoundedRectangleBorder(radius=1)),
        )


class GameContainer(Container):
    def __init__(self, page: Page) -> None:
        super().__init__(
            expand=True,
            bgcolor=CustomColors.ACCENT_COLOR_2,
            visible=True,
            content=Column(
                [
                    Text("GAME", size=40, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
                ],
                expand=True,
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        self.__page = page
        self.__page.update()


class DatabaseContainer(Container):
    def __init__(self, page: Page) -> None:
        super().__init__(
            expand=True,
            bgcolor=CustomColors.ACCENT_COLOR_2,
            visible=False,
            content=Column(
                [
                    Text("DATABASE", size=40, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
                ],
                expand=True,
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        self.__page = page
        self.__page.update()


class LogsContainer(Container):
    def __init__(self, page: Page) -> None:
        super().__init__(
            expand=True,
            bgcolor=CustomColors.ACCENT_COLOR_2,
            visible=False,
            content=Column(
                [
                    Text("LOGS", size=40, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
                ],
                expand=True,
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        self.__page = page
        self.__page.update()


class AboutContainer(Container):
    def __init__(self, page: Page) -> None:
        super().__init__(
            expand=True,
            bgcolor=CustomColors.ACCENT_COLOR_2,
            visible=False,
            content=Column(
                [
                    Image(
                        src="logo.png",
                        width=200,
                        height=200,
                    ),
                    Text(
                        "KawaChess\nEngineering Project",
                        size=40,
                        weight=FontWeight.BOLD,
                        text_align=TextAlign.CENTER,
                    ),
                    Text(
                        "A chess app for Kawasaki FS03N robot",
                        size=12,
                        text_align=TextAlign.CENTER,
                    ),
                    Text(
                        "Made with ❤️ by Jarosław Wierzbowski",
                        size=12,
                        text_align=TextAlign.CENTER,
                    ),
                    Markdown(
                        "[GitHub Repository](https://github.com/Bazyliii/KawaChess)",
                        auto_follow_links=True,
                    ),
                ],
                expand=True,
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        self.__page = page
        self.__page.update()


class SettingsContainer(Container):
    def __init__(self, page: Page) -> None:
        super().__init__(
            expand=True,
            bgcolor=CustomColors.ACCENT_COLOR_2,
            visible=False,
            content=Column(
                [
                    Text("Settings", size=40, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
                ],
                expand=True,
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        self.__page = page
        self.__page.update()


@dataclass(frozen=True)
class CustomColors:
    MAIN_COLOR: str = "#23272E"
    ACCENT_COLOR_1: str = "#1E2227"
    ACCENT_COLOR_2: str = "#0F1113"
    ACCENT_COLOR_3: str = "#4D78CC"


class Containers(Enum):
    GAME = auto()
    DATABASE = auto()
    LOGS = auto()
    SETTINGS = auto()
    ABOUT = auto()


class KawaChessApp:
    def __init__(self, page: Page) -> None:
        self.__page: Page = page
        self.__page.bgcolor = CustomColors.MAIN_COLOR
        self.__page.title = "KawaChess"
        self.__page.window.alignment = alignment.center
        self.__page.window.width = 16 * 80
        self.__page.window.height = 9 * 80
        self.__page.window.title_bar_hidden = True
        self.__page.padding = 0
        self.__page.window.on_event = self.__window_event
        self.__maximize_button: IconButton = MaximizeButton(on_click=lambda _: self.__maximize())
        self.__minimize_button: IconButton = MinimizeButton(on_click=lambda _: self.__minimize())
        self.__close_button: IconButton = CloseButton(on_click=lambda _: self.__close())
        self.__containers: list[Container] = [
            GameContainer(self.__page),
            DatabaseContainer(self.__page),
            LogsContainer(self.__page),
            SettingsContainer(self.__page),
            AboutContainer(self.__page),
        ]
        self.__title_bar = AppBar(
            toolbar_height=32,
            title=WindowDragArea(
                Row(
                    [
                        Text(self.__page.title, color=colors.WHITE, overflow=TextOverflow.ELLIPSIS, expand=True, size=16),
                    ],
                ),
                expand=True,
                maximizable=True,
            ),
            bgcolor=CustomColors.ACCENT_COLOR_1,
            title_spacing=20,
            actions=[
                self.__minimize_button,
                self.__maximize_button,
                self.__close_button,
            ],
        )
        self.__navigation_rail: NavigationRail = NavigationRail(
            destinations=[
                NavigationRailDestination(icon=icons.PLAY_ARROW_OUTLINED, label="Game"),
                NavigationRailDestination(icon=icons.STACKED_LINE_CHART_OUTLINED, label="Database"),
                NavigationRailDestination(icon=icons.RECEIPT_LONG_OUTLINED, label="Logs"),
                NavigationRailDestination(icon=icons.SETTINGS_OUTLINED, label="Settings"),
                NavigationRailDestination(icon=icons.INFO_OUTLINED, label="About"),
            ],
            width=72,
            indicator_shape=RoundedRectangleBorder(radius=7),
            group_alignment=-1,
            label_type=NavigationRailLabelType.ALL,
            selected_index=0,
            bgcolor=CustomColors.ACCENT_COLOR_1,
            indicator_color=CustomColors.ACCENT_COLOR_3,
            on_change=self.__change_container,
        )
        self.__page.add(
            self.__title_bar,
            Row(
                [
                    self.__navigation_rail,
                    self.__containers[0],
                    self.__containers[1],
                    self.__containers[2],
                    self.__containers[3],
                    self.__containers[4],
                ],
                expand=True,
            ),
        )
        self.__page.update()

    def __change_container(self, e: ControlEvent) -> None:
        for container in self.__containers:
            container.visible = False
        self.__containers[e.control.selected_index].visible = True
        self.__page.update()

    def __close(self) -> None:
        self.__page.window.close()

    def __maximize(self) -> None:
        self.__page.window.maximized = not self.__page.window.maximized
        self.__page.update()

    def __minimize(self) -> None:
        self.__page.window.minimized = True
        self.__page.update()

    def __window_event(self, e: ControlEvent) -> None:
        if e.data in {"unmaximize", "maximize"}:
            self.__maximize_button.selected = self.__page.window.maximized
            self.__page.update()


if __name__ == "__main__":
    app(target=KawaChessApp)
