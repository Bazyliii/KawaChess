from collections.abc import Callable

from flet import ButtonStyle, ElevatedButton, IconButton, RoundedRectangleBorder, icons

from kawachess.colors import ACCENT_COLOR_1, ACCENT_COLOR_3, BLUE, GREEN, GREY, RED, WHITE


class Button(ElevatedButton):
    def __init__(self, text: str, on_click: Callable | None = None, icon: str | None = None) -> None:
        super().__init__()
        self.text = text
        self.on_click = on_click
        self.icon = icon
        self.bgcolor = ACCENT_COLOR_1
        self.icon_color = ACCENT_COLOR_3
        self.height = 50
        self.color = WHITE
        self.width = 200
        self.style = ButtonStyle(shape=RoundedRectangleBorder(radius=5))


class CloseButton(IconButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__()
        self.icon = icons.CLOSE
        self.icon_size = 13
        self.on_click = on_click
        self.icon_color = GREY
        self.hover_color = RED
        self.style = ButtonStyle(shape=RoundedRectangleBorder(radius=1))


class MinimizeButton(CloseButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__()
        self.icon = icons.MINIMIZE
        self.on_click = on_click
        self.hover_color = GREEN


class MaximizeButton(CloseButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__()
        self.icon = icons.CHECK_BOX_OUTLINE_BLANK
        self.on_click = on_click
        self.hover_color = GREEN
        self.selected = False
        self.selected_icon = icons.COPY_OUTLINED
        self.hover_color = BLUE
