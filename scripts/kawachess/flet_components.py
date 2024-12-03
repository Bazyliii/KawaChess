from collections.abc import Callable

from flet import ButtonStyle, ElevatedButton, IconButton, RoundedRectangleBorder, icons

from kawachess import colors


class Button(ElevatedButton):
    def __init__(self, text: str, on_click: Callable | None = None, icon: str | None = None) -> None:
        super().__init__()
        self.text = text
        self.on_click = on_click
        self.icon = icon
        self.bgcolor = colors.ACCENT_COLOR_1
        self.icon_color = colors.ACCENT_COLOR_3
        self.height = 50
        self.color = colors.WHITE
        self.width = 200


class CloseButton(IconButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__()
        self.icon = icons.CLOSE
        self.icon_size = 13
        self.on_click = on_click
        self.icon_color = colors.GREY
        self.hover_color = colors.RED
        self.style = ButtonStyle(shape=RoundedRectangleBorder(radius=1))


class MinimizeButton(CloseButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__()
        self.icon = icons.MINIMIZE
        self.on_click = on_click
        self.hover_color = colors.GREEN


class MaximizeButton(CloseButton):
    def __init__(self, on_click: Callable | None = None) -> None:
        super().__init__()
        self.icon = icons.CHECK_BOX_OUTLINE_BLANK
        self.on_click = on_click
        self.hover_color = colors.GREEN
        self.selected = False
        self.selected_icon = icons.COPY_OUTLINED
        self.hover_color = colors.BLUE
