import threading
from base64 import b64encode
from os import getlogin
from time import sleep
from typing import TYPE_CHECKING, Final

from cv2 import CAP_DSHOW, CAP_PROP_FPS, CAP_PROP_FRAME_HEIGHT, CAP_PROP_FRAME_WIDTH, VideoCapture, imencode, resize
from flet import (
    AlertDialog,
    AnimatedSwitcher,
    AnimatedSwitcherTransition,
    AnimationCurve,
    AppBar,
    Column,
    Control,
    ControlEvent,
    CrossAxisAlignment,
    FilterQuality,
    FontWeight,
    Icon,
    IconButton,
    Icons,
    Image,
    MainAxisAlignment,
    Markdown,
    NavigationRail,
    NavigationRailDestination,
    NavigationRailLabelType,
    Page,
    Radio,
    RadioGroup,
    RoundedRectangleBorder,
    Row,
    Slider,
    Text,
    TextAlign,
    TextField,
    TextOverflow,
    TextStyle,
    WindowDragArea,
    alignment,
    app,
)

from kawachess import (
    ACCENT_COLOR_1,
    ACCENT_COLOR_3,
    MAIN_COLOR,
    WHITE,
    Button,
    CloseButton,
    DatabaseContainer,
    GameContainer,
    MaximizeButton,
    MinimizeButton,
    Robot,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

from time import sleep

ROBOT_IP: Final[str] = "192.168.1.155"
ROBOT_PORT: Final[int] = 23
# ROBOT_IP: Final[str] = "127.0.0.1"
# ROBOT_PORT: Final[int] = 9105


class AboutContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.controls = [
            Image(src="logo.png", width=200, height=200),
            Text("KawaChess\nEngineering Project", size=40, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
            Text("A chess app for Kawasaki FS03N robot", size=12, text_align=TextAlign.CENTER),
            Text("Made with ❤️ by Jarosław Wierzbowski", size=12, text_align=TextAlign.CENTER),
            Markdown("[GitHub Repository](https://github.com/Bazyliii/KawaChess)", auto_follow_links=True),
        ]


class Camera(Image):
    def __init__(self) -> None:
        super().__init__()
        self.capture: VideoCapture = VideoCapture(0, CAP_DSHOW)
        self.capture.set(CAP_PROP_FPS, 30)
        self.capture.set(CAP_PROP_FRAME_WIDTH, 720)
        self.capture.set(CAP_PROP_FRAME_HEIGHT, 1280)
        self.width = self.capture.get(CAP_PROP_FRAME_WIDTH)
        self.height = self.capture.get(CAP_PROP_FRAME_HEIGHT)
        self.filter_quality = FilterQuality.NONE
        self.delay: float = 0.5 / 30
        self.__is_mounted = False

    def did_mount(self) -> None:
        self.__is_mounted = True
        self.delay: float = 0.5 / self.capture.get(CAP_PROP_FPS)
        threading.Thread(target=self.get_frames, daemon=True).start()

    def get_frames(self) -> None:
        while True:
            if self.capture.isOpened() and self.capture.read()[0]:
                frame = self.capture.read()[1]
                self.src_base64 = b64encode(imencode(".bmp", frame)[1]).decode("utf-8")
                self.update_when_mounted(self)
            else:
                self.src = "no_camera.png"
                continue
            sleep(self.delay)

    def update_when_mounted(self, control: Control) -> None:
        if self.__is_mounted:
            control.update()

    def will_unmount(self) -> None:
        self.__is_mounted = False


class CameraContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.controls = [
            Camera(),
        ]


class SettingsContainer(Column):
    def __init__(self, robot: Robot, game: GameContainer) -> None:
        super().__init__()
        self.robot: Robot = robot
        self.game: GameContainer = game
        self.expand = True
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.__nickname_field: TextField = TextField(
            width=400,
            text_align=TextAlign.CENTER,
            bgcolor=ACCENT_COLOR_1,
            focused_border_color=ACCENT_COLOR_3,
            border_color=ACCENT_COLOR_1,
            hint_text="Player nickname",
            label="Player nickname",
            focused_border_width=3,
            hint_style=TextStyle(weight=FontWeight.BOLD),
            value=getlogin(),
            on_change=lambda e: self.__control_changed(e, self.game, "player_name"),
        )
        self.__skill_slider: Slider = Slider(
            min=1,
            max=20,
            divisions=19,
            width=400,
            label="{value}",
            value=20,
            thumb_color=ACCENT_COLOR_3,
            active_color=ACCENT_COLOR_3,
            on_change=lambda e: self.__control_changed(e, self.game, "skill_level"),
        )
        self.controls = [
            self.__nickname_field,
            Text("Stockfish skill level:", size=25),
            self.__skill_slider,
            Row(
                [
                    Button(text="Reconnect robot", icon=Icons.REPLAY_OUTLINED, on_click=self.__connect),
                    Button(text="Disconnect robot", icon=Icons.BLOCK_OUTLINED, on_click=self.__disconnect),
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
        ]
        if self.__nickname_field.value is not None:
            self.game.player_name = self.__nickname_field.value
        if self.__skill_slider.value is not None:
            self.game.skill_level = int(self.__skill_slider.value)
        if self.game.player_color is not None:
            self.game.player_color = self.game.player_color

    @staticmethod
    def __control_changed(event: ControlEvent, target_object: object, attribute_name: str | int) -> None:
        setattr(target_object, str(attribute_name), event.control.value)

    def __disconnect(self, *_: object) -> None:
        self.robot.disconnect()

    def __connect(self, *_: object) -> None:
        self.robot.connect()


class KawaChessApp:
    def __init__(self, page: Page) -> None:
        self.__page: Page = page
        self.__robot: Robot = Robot(ROBOT_IP, ROBOT_PORT, self.__show_dialog)
        self.__page.run_thread(self.__robot.connect)
        self.__game_container: GameContainer = GameContainer(600, self.__show_dialog, self.__robot)
        self.__database_container: DatabaseContainer = DatabaseContainer()
        self.__settings_container: SettingsContainer = SettingsContainer(self.__robot, self.__game_container)
        self.__about_container: AboutContainer = AboutContainer()
        self.__camera_container: CameraContainer = CameraContainer()
        self.__maximize_button: IconButton = MaximizeButton(on_click=lambda _: self.__maximize())
        self.__minimize_button: IconButton = MinimizeButton(on_click=lambda _: self.__minimize())
        self.__close_button: IconButton = CloseButton(on_click=self.__close)
        self.__page.bgcolor = MAIN_COLOR
        self.__page.title = "KawaChess"
        self.__page.window.alignment = alignment.center
        self.__page.window.width = 16 * 80
        self.__page.window.height = 9 * 80
        self.__page.window.title_bar_hidden = True
        self.__page.window.always_on_top = True
        self.__page.padding = 0
        self.__page.window.on_event = self.__window_event

        self.__switcher = AnimatedSwitcher(
            self.__game_container,
            transition=AnimatedSwitcherTransition.FADE,
            duration=500,
            reverse_duration=100,
            switch_in_curve=AnimationCurve.EASE_IN,
            switch_out_curve=AnimationCurve.EASE_OUT,
            expand=True,
        )

        self.__title_bar = AppBar(
            toolbar_height=32,
            title=WindowDragArea(
                Row(
                    [
                        Image(src="logo.png", width=16, height=16),
                        Text(self.__page.title, color=WHITE, overflow=TextOverflow.ELLIPSIS, expand=True, size=16),
                    ],
                ),
                expand=True,
                maximizable=True,
            ),
            bgcolor=ACCENT_COLOR_1,
            elevation_on_scroll=0,
            elevation=0,
            title_spacing=10,
            actions=[self.__minimize_button, self.__maximize_button, self.__close_button],
        )
        self.__navigation_rail: NavigationRail = NavigationRail(
            destinations=[
                NavigationRailDestination(icon=Icons.PLAY_ARROW_OUTLINED, label="Game"),
                NavigationRailDestination(icon=Icons.STACKED_LINE_CHART_OUTLINED, label="Database"),
                NavigationRailDestination(icon=Icons.SETTINGS_OUTLINED, label="Settings"),
                NavigationRailDestination(icon=Icons.CAMERA_ALT_OUTLINED, label="Camera"),
                NavigationRailDestination(icon=Icons.INFO_OUTLINED, label="About"),
            ],
            width=72,
            indicator_shape=RoundedRectangleBorder(radius=5),
            group_alignment=-1,
            label_type=NavigationRailLabelType.ALL,
            selected_index=0,
            bgcolor=ACCENT_COLOR_1,
            indicator_color=ACCENT_COLOR_3,
            on_change=self.__change_container,
        )
        self.__page.controls = [
            self.__title_bar,
            Row(
                [
                    self.__navigation_rail,
                    self.__switcher,
                ],
                expand=True,
                spacing=0,
            ),
        ]
        self.__page.update()

    def __change_container(self, e: ControlEvent) -> None:
        match e.control.selected_index:
            case 0:
                self.__switcher.content = self.__game_container
            case 1:
                self.__switcher.content = self.__database_container
            case 2:
                self.__switcher.content = self.__settings_container
            case 3:
                self.__switcher.content = self.__camera_container
            case 4:
                self.__switcher.content = self.__about_container
        self.__switcher.update()

    def __close(self, *_: object) -> None:
        self.__game_container.close()
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

    def __show_dialog(self, msg: str) -> None:
        dialog = AlertDialog(
            shape=RoundedRectangleBorder(radius=5),
            content=Text(msg, text_align=TextAlign.CENTER, size=27),
            bgcolor=ACCENT_COLOR_1,
            icon=Icon(Icons.INFO_OUTLINED, size=42, color=ACCENT_COLOR_3),
        )
        self.__page.overlay.append(dialog)
        dialog.open = True
        self.__page.update()


if __name__ == "__main__":
    app(target=KawaChessApp)
