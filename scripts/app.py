import flet
from flet import (
    AlertDialog,
    AppBar,
    BorderSide,
    ButtonStyle,
    ClipBehavior,
    Column,
    Container,
    ControlEvent,
    CrossAxisAlignment,
    DataCell,
    DataColumn,
    DataRow,
    DataTable,
    Divider,
    ElevatedButton,
    FontWeight,
    Icon,
    IconButton,
    Image,
    ListView,
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
    VerticalDivider,
    WindowDragArea,
    alignment,
    app,
    border,
    border_radius,
    icons,
    padding,
)
from kawachess import ChessDatabase, GameContainer, RobotCommand, RobotConnection, RobotStatus, colors, flet_components


class DatabaseContainer(Column):
    def __init__(self) -> None:
        super().__init__()
        self.expand = True
        self.visible = False
        self.scroll = ScrollMode.ADAPTIVE

    def update_game_data(self) -> None:
        # database = ChessDatabase("chess.db")
        with ChessDatabase("chess.db") as database:
            self.controls = (
                DataTable(
                    columns=[
                        DataColumn(Text("ID"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("White Player"), heading_row_alignment=MainAxisAlignment.CENTER),
                        DataColumn(Text("Black Player"), heading_row_alignment=MainAxisAlignment.CENTER),
                    DataColumn(Text("Date"), heading_row_alignment=MainAxisAlignment.CENTER),
                    DataColumn(Text("Duration"), heading_row_alignment=MainAxisAlignment.CENTER),
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
        # database.close()
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
    def __init__(self, robot: RobotConnection) -> None:
        super().__init__()
        self.robot: RobotConnection = robot
        self.expand = True
        self.visible = False
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.controls = [
            TextField(
                width=400,
                text_align=TextAlign.CENTER,
                bgcolor=colors.ACCENT_COLOR_1,
                focused_border_color=colors.ACCENT_COLOR_3,
                border_color=colors.ACCENT_COLOR_1,
                hint_text="Player nickname",
                focused_border_width=3,
                hint_style=TextStyle(weight=FontWeight.BOLD),
            ),
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
            Slider(
                min=1,
                max=20,
                divisions=19,
                width=400,
                label="{value}",
                value=20,
                thumb_color=colors.ACCENT_COLOR_3,
                active_color=colors.ACCENT_COLOR_3,
            ),
            Row(
                [
                    flet_components.Button(
                        text="Reconnect robot",
                        icon=icons.REPLAY_OUTLINED,
                        on_click=lambda _: self.robot.login(),
                    ),
                    flet_components.Button(
                        text="Disconnect robot",
                        icon=icons.REPLAY_OUTLINED,
                        on_click=lambda _: self.robot.close(),
                    ),
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
        ]


class KawaChessApp:
    def __init__(self, page: Page) -> None:
        self.__page: Page = page
        self.__robot: RobotConnection = RobotConnection("127.0.0.1/9105", self.__show_dialog)
        self.__page.bgcolor = colors.MAIN_COLOR
        self.__page.title = "KawaChess"
        self.__page.window.alignment = alignment.center
        self.__page.window.width = 16 * 80
        self.__page.window.height = 9 * 80
        self.__page.window.title_bar_hidden = True
        self.__page.window.always_on_top = True
        self.__page.padding = 0
        self.__page.window.on_event = self.__window_event
        self.__maximize_button: IconButton = flet_components.MaximizeButton(on_click=lambda _: self.__maximize())
        self.__minimize_button: IconButton = flet_components.MinimizeButton(on_click=lambda _: self.__minimize())
        self.__close_button: IconButton = flet_components.CloseButton(on_click=lambda _: self.__close())
        self.__containers: list = [
            GameContainer(420, self.__show_dialog, self.__robot, 20),
            DatabaseContainer(),
            LogsContainer(),
            SettingsContainer(self.__robot),
            AboutContainer(),
        ]
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
                spacing=0,
            ),
        )
        self.__page.update()

    def __change_container(self, e: ControlEvent) -> None:
        match e.control.selected_index:
            case 1:
                self.__containers[1].update_game_data()
        for container in self.__containers:
            container.visible = False
        self.__containers[e.control.selected_index].visible = True
        self.__page.update()

    def __close(self) -> None:
        self.__containers[0].close()
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
        )
        self.__page.overlay.append(dialog)
        dialog.open = True
        self.__page.update()


if __name__ == "__main__":
    app(target=KawaChessApp)
