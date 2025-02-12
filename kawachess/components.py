from collections.abc import Callable

from flet import ButtonStyle, ControlState, ElevatedButton, IconButton, Icons, RoundedRectangleBorder

from kawachess.constants import ACCENT_COLOR_1, ACCENT_COLOR_2, ACCENT_COLOR_3, BLUE, GREEN, GREY, RED, WHITE


class Button(ElevatedButton):
    def __init__(self, text: str, on_click: Callable | None = None, icon: str | None = None, disabled: bool = False) -> None:
        super().__init__()
        self.text = text
        self.on_click = on_click
        self.icon = icon
        self.height = 50
        self.width = 200
        self.style = ButtonStyle(
            shape=RoundedRectangleBorder(radius=5),
            bgcolor={ControlState.DISABLED: ACCENT_COLOR_2, ControlState.DEFAULT: ACCENT_COLOR_1},
            icon_color={ControlState.DISABLED: ACCENT_COLOR_1, ControlState.DEFAULT: ACCENT_COLOR_3},
            color={ControlState.DISABLED: ACCENT_COLOR_1, ControlState.DEFAULT: WHITE},
        )
        self.disabled = disabled


class CloseButton(IconButton):
    def __init__(self, on_click: Callable[..., None] | None = None) -> None:
        super().__init__()
        self.icon = Icons.CLOSE
        self.icon_size = 13
        self.on_click = on_click
        self.icon_color = GREY
        self.hover_color = RED
        self.style = ButtonStyle(shape=RoundedRectangleBorder(radius=1))


class MinimizeButton(CloseButton):
    def __init__(self, on_click: Callable[..., None] | None = None) -> None:
        super().__init__()
        self.icon = Icons.MINIMIZE
        self.on_click = on_click
        self.hover_color = GREEN


class MaximizeButton(CloseButton):
    def __init__(self, on_click: Callable[..., None] | None = None) -> None:
        super().__init__()
        self.icon = Icons.CHECK_BOX_OUTLINE_BLANK
        self.on_click = on_click
        self.selected = False
        self.selected_icon = Icons.COPY_OUTLINED
        self.hover_color = BLUE
