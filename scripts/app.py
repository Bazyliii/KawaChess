from os import getlogin

from flet import (
    AlertDialog,
    AppBar,
    BorderSide,
    Column,
    ControlEvent,
    CrossAxisAlignment,
    DataCell,
    DataColumn,
    DataRow,
    DataTable,
    FontWeight,
    Icon,
    IconButton,
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
    ScrollMode,
    Slider,
    Text,
    TextAlign,
    TextField,
    TextOverflow,
    TextStyle,
    WindowDragArea,
    alignment,
    app,
    icons,
)
from kawachess import ChessDatabase, GameContainer, RobotConnection, colors
from kawachess.flet_components import Button, CloseButton, MaximizeButton, MinimizeButton


class DatabaseContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.visible = False
        self.scroll = ScrollMode.ADAPTIVE
        self.height = 10000

    def update_game_data(self) -> None:
        with ChessDatabase("chess.db") as database:
            self.controls = (
                DataTable(
                    columns=[
                        DataColumn(Text("ID"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("White Player"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Black Player"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Date"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Duration"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Stockfish Skill"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Result"), heading_row_alignment=MainAxisAlignment.CENTER),
                    ],
                    rows=[
                        DataRow(
                            cells=[
                                DataCell(Text(str(row[0]))),
                                DataCell(Text(row[1])),
                                DataCell(Text(row[2])),
                                DataCell(Text(row[3])),
                                DataCell(Text(row[4])),
                                DataCell(Text(str(row[6]))),
                                DataCell(Text(row[10])),
                            ],
                        )
                        for row in database.get_game_data()
                    ],
                    width=10000,
                    sort_column_index=0,
                    data_row_max_height=50,
                    vertical_lines=BorderSide(2, colors.ACCENT_COLOR_1),
                    horizontal_lines=BorderSide(2, colors.ACCENT_COLOR_1),
                    heading_row_color=colors.ACCENT_COLOR_1,
                    heading_text_style=TextStyle(
                        weight=FontWeight.BOLD,
                        color=colors.ACCENT_COLOR_3,
                    ),
                ),
            )
        self.update()


class LogsContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.bgcolor: str = colors.ACCENT_COLOR_2
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.visible = False
        self.controls = [
            Text("LOGS", size=40, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
        ]


class AboutContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.visible = False
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.controls = [
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
        ]


class SettingsContainer(Column):
    def __init__(self, robot: RobotConnection, game: GameContainer) -> None:
        super().__init__()
        self.robot: RobotConnection = robot
        self.game: GameContainer = game
        self.expand = True
        self.visible = False
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.__nickname_field: TextField = TextField(
            width=400,
            text_align=TextAlign.CENTER,
            bgcolor=colors.ACCENT_COLOR_1,
            focused_border_color=colors.ACCENT_COLOR_3,
            border_color=colors.ACCENT_COLOR_1,
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
                thumb_color=colors.ACCENT_COLOR_3,
                active_color=colors.ACCENT_COLOR_3,
                on_change=lambda e: self.__control_changed(e, self.game, "skill_level"),
            )
        self.controls = [
            self.__nickname_field,
            Text("Player piece color:", size=25),
            RadioGroup(
                content=Row(
                    [
                        Radio(
                            value="white",
                            label="White",
                            active_color=colors.ACCENT_COLOR_3,
                        ),
                        Radio(
                            value="black",
                            label="Black",
                            active_color=colors.ACCENT_COLOR_3,
                        ),
                        Radio(
                            value="random",
                            label="Random",
                            active_color=colors.ACCENT_COLOR_3,
                        ),
                    ],
                    alignment=MainAxisAlignment.CENTER,
                ),
                value="random",
            ),
            Text("Stockfish skill level:", size=25),
            self.__skill_slider,
            Row(
                [
                    Button(
                        text="Reconnect robot",
                        icon=icons.REPLAY_OUTLINED,
                        on_click=lambda _: self.robot.login(),
                    ),
                    Button(
                        text="Disconnect robot",
                        icon=icons.BLOCK_OUTLINED,
                        on_click=lambda _: self.robot.close(),
                    ),
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
        ]
        if self.__nickname_field.value is not None:
            self.game.player_name = self.__nickname_field.value
        if self.__skill_slider.value is not None:
            self.game.skill_level = int(self.__skill_slider.value)

    @staticmethod
    def __control_changed(event: ControlEvent, target_object: object, attribute_name: str | int) -> None:
        setattr(target_object, str(attribute_name), event.control.value)


class KawaChessApp:
    def __init__(self, page: Page) -> None:
        self.__page: Page = page
        self.__robot: RobotConnection = RobotConnection("127.0.0.1/9105", self.__show_dialog)
        self.__game_container: GameContainer = GameContainer(420, self.__show_dialog, self.__robot)
        self.__database_container: DatabaseContainer = DatabaseContainer()
        self.__logs_container: LogsContainer = LogsContainer()
        self.__settings_container: SettingsContainer = SettingsContainer(self.__robot, self.__game_container)
        self.__about_container: AboutContainer = AboutContainer()
        self.__maximize_button: IconButton = MaximizeButton(on_click=lambda _: self.__maximize())
        self.__minimize_button: IconButton = MinimizeButton(on_click=lambda _: self.__minimize())
        self.__close_button: IconButton = CloseButton(on_click=lambda _: self.__close())
        self.__page.bgcolor = colors.MAIN_COLOR
        self.__page.title = "KawaChess"
        self.__page.window.alignment = alignment.center
        self.__page.window.width = 16 * 80
        self.__page.window.height = 9 * 80
        self.__page.window.title_bar_hidden = True
        self.__page.window.always_on_top = True
        self.__page.padding = 0
        self.__page.window.on_event = self.__window_event
        self.__title_bar = AppBar(
            toolbar_height=32,
            title=WindowDragArea(
                Row(
                    [
                        Image(src="logo.png", width=16, height=16),
                        Text(self.__page.title, color=colors.WHITE, overflow=TextOverflow.ELLIPSIS, expand=True, size=16),
                    ],
                ),
                expand=True,
                maximizable=True,
            ),
            bgcolor=colors.ACCENT_COLOR_1,
            elevation_on_scroll=0,
            elevation=0,
            title_spacing=10,
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
            indicator_shape=RoundedRectangleBorder(radius=5),
            group_alignment=-1,
            label_type=NavigationRailLabelType.ALL,
            selected_index=0,
            bgcolor=colors.ACCENT_COLOR_1,
            indicator_color=colors.ACCENT_COLOR_3,
            on_change=self.__change_container,
        )
        self.__page.controls = [
            self.__title_bar,
            Row(
                [
                    self.__navigation_rail,
                    self.__game_container,
                    self.__database_container,
                    self.__logs_container,
                    self.__settings_container,
                    self.__about_container,
                ],
                expand=True,
                spacing=0,
            ),
        ]
        self.__page.update()

    def __change_container(self, e: ControlEvent) -> None:
        if not self.__page.controls:
            return
        index: int = e.control.selected_index
        if index == 1:
            self.__database_container.update_game_data()
        for container in self.__page.controls[1].controls[1:]:
            container.visible = not container is not self.__page.controls[1].controls[index + 1]
        self.__page.update()

    def __close(self) -> None:
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
            bgcolor=colors.ACCENT_COLOR_1,
            icon=Icon(icons.INFO_OUTLINED, size=42, color=colors.ACCENT_COLOR_3),
        )
        self.__page.overlay.append(dialog)
        dialog.open = True
        self.__page.update()


if __name__ == "__main__":
    app(target=KawaChessApp)
