import base64
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from os.path import exists
from socket import socket
from sqlite3 import Connection, Cursor, connect
from telnetlib import DO, ECHO, IAC, SB, SE, TTYPE, WILL, Telnet  # noqa: S401
from time import sleep
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal

import cv2
from chess import Board, Move, svg
from chess.engine import Limit, SimpleEngine
from chess.pgn import Game
from flet import (
    AppBar,
    ButtonStyle,
    ClipBehavior,
    Column,
    Container,
    ControlEvent,
    CrossAxisAlignment,
    FontWeight,
    IconButton,
    Image,
    ListView,
    MainAxisAlignment,
    Page,
    RoundedRectangleBorder,
    Row,
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
    colors,
    icons,
)
from flet_timer.flet_timer import Timer
from numpy import ndarray
from pytz import timezone
from pytz.tzinfo import BaseTzInfo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cv2.aruco import DetectorParameters, Dictionary

TIMEZONE: Final[BaseTzInfo] = timezone("Europe/Warsaw")
TIMEOUT: Final[int] = 5
ENTER: Final[bytes] = b"\n\r\n"
ENDLINE: Final[bytes] = b"\r\n"
ENCODING: Final[str] = "ascii"


@dataclass(frozen=True)
class MessageType:
    ERROR: tuple[Literal["[ERROR] "], Literal["red400"]] = ("[ERROR] ", colors.RED_400)
    WARNING: tuple[Literal["[WARNING] "], Literal["orange400"]] = ("[WARNING] ", colors.ORANGE_400)
    INFO: tuple[Literal["[INFO] "], Literal["green400"]] = ("[INFO] ", colors.GREEN_400)
    EXCEPTION: tuple[Literal["[EXCEPTION] "], Literal["red400"]] = ("[EXCEPTION] ", colors.RED_400)
    GAME_STATUS: tuple[Literal["[GAME STATUS] "], Literal["yellow600"]] = ("[GAME STATUS] ", colors.YELLOW_600)
    MOVE: tuple[Literal["[MOVE] "], Literal["green400"]] = ("[MOVE] ", colors.GREEN_400)


@dataclass(frozen=True)
class RobotCommand:
    RESET: Final[tuple[str, int]] = ("ERESET", 0)
    MOTOR_ON: Final[tuple[str, int]] = ("ZPOW ON", 0)
    MOTOR_OFF: Final[tuple[str, int]] = ("ZPOW OFF", 0)
    HOME: Final[tuple[str, int]] = ("DO HOME", 1)
    MOVE_TO_POINT: Final[tuple[str, int]] = ("DO LMOVE", 1)
    PICKUP: Final[tuple[str, int]] = ("DO LDEPART 80", 1)
    PUTDOWN: Final[tuple[str, int]] = ("DO LDEPART -80", 1)
    EXECUTE_PROG: Final[tuple[str, int]] = ("EXE", 2)
    CONTINUOUS_PATH_ON: Final[tuple[str, int]] = ("CP ON", 0)
    CONTINUOUS_PATH_OFF: Final[tuple[str, int]] = ("CP OFF", 0)


class RobotStatus(Enum):
    ERROR = 0
    MOTOR_POWERED = 1
    REPEAT_MODE = 2
    TEACH_MODE = 3
    TEACH_LOCK = 4
    BUSY = 5
    HOLD = 6
    CONTINUOUS_PATH = 7


class RobotConnection:
    __USER: ClassVar[str] = "as"

    def __init__(self, ip: str, port: int) -> None:
        self.__ip: str = ip
        self.__port: int = port
        self.__telnet: Final[Telnet] = Telnet()  # noqa: S312
        self.__telnet.set_option_negotiation_callback(self.__negotiation)
        self.connect()

    def connect(self) -> None:
        self.__telnet.open(self.__ip, self.__port, TIMEOUT)
        _ = self.__telnet.read_until(b"login: ")
        self.__telnet.write(self.__USER.encode(ENCODING) + ENDLINE)
        _ = self.__telnet.read_until(b">")

    def disconnect(self) -> None:
        self.__telnet.write(b"KILL" + ENDLINE)
        self.__telnet.write(b"1" + ENDLINE)
        self.__telnet.write(ENTER)
        self.__telnet.close()

    @staticmethod
    def __negotiation(socket: socket, cmd: bytes, opt: bytes) -> None:
        if cmd == WILL and opt == ECHO:
            socket.sendall(IAC + DO + opt)
        elif cmd == DO and opt == TTYPE:
            socket.sendall(IAC + WILL + TTYPE)
        elif cmd == SB:
            socket.sendall(IAC + SB + TTYPE + b"\00" + b"VT100" + b"\00" + IAC + SE)

    @property
    def telnet(self) -> Telnet:
        return self.__telnet


class JointState:
    def __init__(self, connection: RobotConnection, jt1: float, jt2: float, jt3: float, jt4: float, jt5: float, jt6: float, name: str) -> None:  # noqa: PLR0917 PLR0913
        self.__connection: Final[RobotConnection] = connection
        self.__telnet: Final[Telnet] = connection.telnet
        self.jt1: float = jt1
        self.jt2: float = jt2
        self.jt3: float = jt3
        self.jt4: float = jt4
        self.jt5: float = jt5
        self.jt6: float = jt6
        self.name: str = name
        self.create_joint_point()
        self.X, self.Y, self.Z, self.O, self.A, self.T = map(float, self.translate_joint_to_cartesian()[:6])

    def create_joint_point(self) -> None:
        self.__telnet.write(f"POINT #{self.name}".encode(ENCODING) + ENDLINE)
        self.__telnet.write(f"{self.jt1},{self.jt2},{self.jt3},{self.jt4},{self.jt5},{self.jt6}".encode(ENCODING))
        self.__telnet.write(ENTER)

    def translate_joint_to_cartesian(self) -> list[float]:
        self.__telnet.write(f"POINT {self.name}=#{self.name}".encode(ENCODING) + ENDLINE)
        time.sleep(0.1)  # FIXME
        x: list[float] = [
            float(i) for i in filter(None, self.__telnet.read_very_eager().decode(ENCODING).split(f"{self.name}=#{self.name}")[1].splitlines()[2].split(" "))
        ]
        self.__telnet.write(ENTER)
        return x

    def shift_point(self, x: float, y: float, z: float, name: str) -> "JointState":
        self.__telnet.write(f"POINT {name} = SHIFT({self.name} by {x},{y},{z})".encode(ENCODING) + ENDLINE)
        self.__telnet.write(ENTER)
        self.__telnet.write(f"POINT #{name}={name}".encode(ENCODING) + ENDLINE)
        time.sleep(0.1)  # FIXME
        jt: list[float] = [
            float(i) for i in filter(None, self.__telnet.read_very_eager().decode(ENCODING).split(f"#{name}={name}")[1].splitlines()[2].split(" "))
        ]
        self.__telnet.write(ENTER)
        return JointState(self.__connection, jt[0], jt[1], jt[2], jt[3], jt[4], jt[5], name)


class RobotControl:
    __SPEED: ClassVar[int] = 100

    def __init__(self, connection: RobotConnection) -> None:
        self.__telnet: Final[Telnet] = connection.telnet
        self.initial_status: dict[RobotStatus, bool] = self.get_robot_status()
        if self.initial_status[RobotStatus.ERROR]:
            self.send_command(RobotCommand.RESET)
        if self.initial_status[RobotStatus.CONTINUOUS_PATH]:
            self.send_command(RobotCommand.CONTINUOUS_PATH_OFF)
        if not self.initial_status[RobotStatus.MOTOR_POWERED]:
            self.send_command(RobotCommand.MOTOR_ON)
        self.write_program("""SPEED 100 ALWAYS\n""", "chess_program")
        self.send_command(RobotCommand.EXECUTE_PROG, "chess_program")
        self.__home: Final[JointState] = JointState(connection, 9.487, 68.678, -53.954, -179.435, 57.988, -237.583, "chess_app_temp_point")

    def calculate_chessboard_point_to_move(self, chessboard_uci: str, z: float = 0.0) -> JointState:
        x: int = ord(chessboard_uci[0]) - ord("a")
        y: int = int(chessboard_uci[1]) - 1
        return self.__home.shift_point(x * -40, y * -40, z, chessboard_uci)

    def get_robot_status(self) -> dict[RobotStatus, bool]:
        self.__telnet.write(b"SWITCH" + ENDLINE)
        raw_msg: str = self.__telnet.read_until(b"Press SPACE key to continue").decode(ENCODING).split("SWITCH\r")[1]
        raw_data: list[str | Any] = [s.replace(" ", "").replace("\n", "").replace("*", "").replace("\r", "") for s in re.split(" ON| OFF", raw_msg)]
        raw_data.pop()
        status_data: dict[str, bool] = {key: value == " ON" for key, value in zip(raw_data, re.findall(" ON| OFF", raw_msg), strict=False)}
        time.sleep(0.1)  # FIXME
        self.__telnet.write(ENTER)

        status: dict[RobotStatus, bool] = {
            RobotStatus.BUSY: False,
            RobotStatus.ERROR: False,
            RobotStatus.MOTOR_POWERED: False,
            RobotStatus.REPEAT_MODE: False,
            RobotStatus.TEACH_MODE: False,
            RobotStatus.TEACH_LOCK: False,
            RobotStatus.HOLD: False,
            RobotStatus.CONTINUOUS_PATH: False,
        }
        try:
            status[RobotStatus.BUSY] = status_data["CS"]
            status[RobotStatus.ERROR] = status_data["ERROR"]
            status[RobotStatus.MOTOR_POWERED] = status_data["POWER"]
            status[RobotStatus.REPEAT_MODE] = status_data["REPEAT"]
            status[RobotStatus.TEACH_MODE] = not status_data["REPEAT"]
            status[RobotStatus.TEACH_LOCK] = status_data["TEACH_LOCK"]
            status[RobotStatus.HOLD] = not status_data["RUN"]
            status[RobotStatus.CONTINUOUS_PATH] = status_data["CP"]
        except KeyError:
            pass
        return status


    def write_program(self, program: str, name: str) -> None:
        self.__telnet.write(b"KILL" + ENDLINE)
        self.__telnet.write(b"1" + ENDLINE)
        self.__telnet.write(ENTER)
        self.__telnet.write(f"DELETE {name}".encode(ENCODING) + ENDLINE)
        self.__telnet.write(b"1" + ENDLINE)
        self.__telnet.write(ENTER)
        self.__telnet.write(f"EDIT {name}, 1".encode(ENCODING) + ENDLINE)
        for line in program.splitlines():
            self.__telnet.write(line.encode(ENCODING) + ENDLINE)
        self.__telnet.write(b"E")
        self.__telnet.write(ENTER)
        time.sleep(0.1)  # FIXME

    def send_command(self, command: tuple[str, int], arg: JointState | str | None = None) -> None:
        command_encoded: bytes = command[0].encode(ENCODING)
        match command[1]:
            case 0:
                self.__telnet.write(command_encoded + ENDLINE)
                _ = self.__telnet.read_until(b">")
            case 1:
                if type(arg) is JointState:
                    self.__telnet.write(command_encoded + f" #{arg.name}".encode(ENCODING) + ENDLINE)
                    _ = self.__telnet.read_until(b">")
                else:
                    self.__telnet.write(command_encoded + ENDLINE)
                    _ = self.__telnet.read_until(b"DO motion completed.")
            case 2:
                self.__telnet.write(command_encoded + f" {arg}".encode(ENCODING) + ENDLINE)
                _ = self.__telnet.read_until(b"Program completed.")
        time.sleep(0.5)  # FIXME


class Logger:
    def __init__(self, width: int) -> None:
        self.__log_container = ListView(
            width=width,
            clip_behavior=ClipBehavior.NONE,
            auto_scroll=True,
            spacing=1,
            divider_thickness=1,
        )

    def __call__(self, msg_type: tuple[str, str], text: str | Exception) -> None:
        self.__log_container.controls.append(
            Text(
                spans=[
                    TextSpan(datetime.now(TIMEZONE).strftime("%H:%M:%S "), TextStyle(color=colors.WHITE38)),
                    TextSpan(msg_type[0], TextStyle(weight=FontWeight.BOLD)),
                    TextSpan(str(text)),
                ],
                color=msg_type[1],
            ),
        )
        self.__log_container.update()

    def clear(self) -> None:
        self.__log_container.controls.clear()
        self(MessageType.WARNING, "Log cleared!")

    @property
    def log_container(self) -> ListView:
        return self.__log_container


class ChessDatabase:
    def __init__(self, name: str) -> None:
        self.name: str = name
        if not exists(self.name):
            self.connection: Connection = connect(self.name, check_same_thread=False)
            self.cursor: Cursor = self.connection.cursor()
            for query in (
                """
                CREATE TABLE IF NOT EXISTS results(
                    id INTEGER,
                    name TEXT NOT NULL,
                    CONSTRAINT results_pk PRIMARY KEY (id)
                );""",
                """
                INSERT INTO results(name)
                    VALUES  ("NO RESULT"),
                            ("WHITE WIN"),
                            ("BLACK WIN"),
                            ("DRAW BY FIVEFOLD REPETITION"),
                            ("DRAW BY STALEMATE"),
                            ("DRAW BY FIFTY-MOVE RULE"),
                            ("DRAW BY INSUFFICIENT MATERIAL"),
                            ("DRAW");
                """,
                """
                CREATE TABLE IF NOT EXISTS chess_games(
                    id INTEGER NOT NULL,
                    white_player TEXT NOT NULL,
                    black_player TEXT NOT NULL,
                    date TEXT NOT NULL,
                    game_duration TEXT NOT NULL,
                    result_id INTEGER NOT NULL,
                    stockfish_skill_level INTEGER NOT NULL,
                    move_count INTEGER NOT NULL,
                    FEN_end_position TEXT NOT NULL,
                    PGN_game_sequence TEXT NOT NULL,
                    CONSTRAINT chess_games_pk PRIMARY KEY (id)
                    CONSTRAINT results_fk FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE CASCADE ON UPDATE CASCADE
                );
                """,
            ):
                self.cursor.execute(query)
            self.connection.commit()
        else:
            self.connection: Connection = connect(self.name, check_same_thread=False)
            self.cursor: Cursor = self.connection.cursor()

    def close(self) -> None:
        if self.connection:
            self.connection.close()

    @staticmethod
    def get_game_results(board: Board) -> Literal[1, 2, 3, 4, 5, 6, 7, 8]:
        match Game().from_board(board).headers["Result"]:
            case "1-0":
                result = 2
            case "0-1":
                result = 3
            case "1/2-1/2":
                if board.is_fivefold_repetition():
                    result = 4
                if board.is_stalemate():
                    result = 5
                if board.is_fifty_moves():
                    result = 6
                if board.is_insufficient_material():
                    result = 7
                result = 8
            case _:
                result = 1
        return result

    def add_game_data(
        self,
        board: Board,
        start_datetime: datetime,
        duration: timedelta,
        stockfish_skill_level: int,
        players: tuple[str, ...] = ("Stockfish", "Player"),
    ) -> None:
        game: Game = Game().from_board(board)
        self.cursor.execute(
            """
            INSERT INTO chess_games(white_player, black_player, date, game_duration, result_id,stockfish_skill_level ,move_count, FEN_end_position, PGN_game_sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,  # noqa: E501
            (
                players[0],
                players[1],
                start_datetime.strftime("%d-%m-%Y %H:%M:%S"),
                str(duration - timedelta(seconds=1)),
                self.get_game_results(board),
                stockfish_skill_level,
                board.fullmove_number,
                board.fen(),
                str(game.mainline_moves()),
            ),
        )
        self.connection.commit()


class OpenCVCapture(Image):
    def __init__(self, height: int, width: int) -> None:
        super().__init__()
        self.capture = cv2.VideoCapture(0)
        self.__wait_time: float = self.capture.get(cv2.CAP_PROP_FPS) / 1000
        self.__height: int = height
        self.__width: int = width
        self.__resize: tuple[int, int] = (self.__width, self.__height)
        self.__aruco_dict: Dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.__aruco_params: DetectorParameters = cv2.aruco.DetectorParameters()
        self.__aruco_detector: cv2.aruco.ArucoDetector = cv2.aruco.ArucoDetector(self.__aruco_dict, self.__aruco_params)
        self.__aruco_pieces_ids: dict = {
            **dict.fromkeys(range(8), "White Pawn"),
            **dict.fromkeys([8, 9], "White Rook"),
            **dict.fromkeys([10, 11], "White Rook"),
            **dict.fromkeys([12, 13], "White Rook"),
            14: "White Queen",
            15: "White King",
            **dict.fromkeys(range(16, 24), "Black Pawn"),
            **dict.fromkeys([24, 25], "Black Rook"),
            **dict.fromkeys([26, 27], "Black Rook"),
            **dict.fromkeys([28, 29], "Black Rook"),
            30: "Black Queen",
            31: "Black King",
            **dict.fromkeys(range(32, 99), "Not defined"),
        }

    def draw_aruco_marker(self, frame: ndarray) -> ndarray:
        marker_data: tuple = self.__aruco_detector.detectMarkers(frame)
        corners: Sequence[ndarray] = marker_data[0]
        if len(corners) > 0:
            ids: ndarray = marker_data[1].flatten()
            for marker_corner, marker_id in zip(corners, ids, strict=False):
                corners_reshaped: ndarray = marker_corner.reshape((4, 2))
                (top_left, top_right, bottom_right, bottom_left) = corners_reshaped

                top_right: tuple[int, int] = (int(top_right[0]), int(top_right[1]))
                bottom_right: tuple[int, int] = (int(bottom_right[0]), int(bottom_right[1]))
                bottom_left: tuple[int, int] = (int(bottom_left[0]), int(bottom_left[1]))
                top_left: tuple[int, int] = (int(top_left[0]), int(top_left[1]))

                cv2.line(frame, top_left, top_right, (80, 127, 255), 2)
                cv2.line(frame, top_right, bottom_right, (80, 127, 255), 2)
                cv2.line(frame, bottom_right, bottom_left, (80, 127, 255), 2)
                cv2.line(frame, bottom_left, top_left, (80, 127, 255), 2)

                cx = int((top_left[0] + bottom_right[0]) / 2.0)
                cy = int((top_left[1] + bottom_right[1]) / 2.0)

                cv2.circle(frame, (cx, cy), 4, (255, 127, 80), -1)

                # cv2.putText(frame, self.__aruco_pieces_ids[marker_id], (top_left[0], top_left[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 2)
        return frame

    def did_mount(self) -> None:
        while True:
            frame: ndarray = self.capture.read()[1]
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            frame = cv2.resize(frame, self.__resize)
            frame = self.draw_aruco_marker(frame)
            self.src_base64 = base64.b64encode(cv2.imencode(".png", frame)[1]).decode("utf-8")
            self.update()
            sleep(self.__wait_time)

    def build(self) -> None:
        self.img = Image(height=self.__height, width=self.__width)

    def __del__(self) -> None:
        self.capture.release()


class GameLogic:
    def __init__(self, board_width: int, board_height: int, logger: Logger, database: ChessDatabase, page: Page) -> None:
        self.logger: Logger = logger
        self.database: ChessDatabase = database
        self.connection: RobotConnection = RobotConnection("192.168.1.155", 23)
        self.robot: RobotControl = RobotControl(self.connection)
        self.__page: Page = page
        self.__game_status: bool = False
        self.__stockfish_skill_level: int = 20
        self.__game_stockfish_skill_lvl: int
        self.__chess_board_svg: Image = Image(src=svg.board(Board()), width=board_width, height=board_height)
        self.__start_datetime: datetime
        self.__game_duration: timedelta = timedelta()
        self.__player_name: str = "Player"

    @property
    def start_datetime(self) -> datetime:
        return self.__start_datetime

    @property
    def player_name(self) -> str:
        return self.__player_name

    @property
    def chess_board_svg(self) -> Image:
        return self.__chess_board_svg

    @property
    def game_status(self) -> bool:
        return self.__game_status

    @property
    def game_duration(self) -> timedelta:
        return self.__game_duration

    @game_duration.setter
    def game_duration(self, value: timedelta) -> None:
        self.__game_duration = value

    @player_name.setter
    def player_name(self, value: str) -> None:
        self.__player_name = value

    @game_status.setter
    def game_status(self, value: bool) -> None:
        self.__game_status = value

    @property
    def stockfish_skill_level(self) -> int:
        return self.__stockfish_skill_level

    @stockfish_skill_level.setter
    def stockfish_skill_level(self, value: int) -> None:
        self.__stockfish_skill_level = value

    def start_game(self) -> None:
        if self.__game_status:
            return
        self.__start_datetime = datetime.now(TIMEZONE)
        self.logger(MessageType.GAME_STATUS, "Game started!")
        self.__game_status = True
        self.__engine: SimpleEngine = SimpleEngine.popen_uci(r"stockfish\stockfish-windows-x86-64-avx2.exe")
        self.__engine.configure({"Threads": "2", "Hash": "512", "Skill Level": self.__stockfish_skill_level})
        self.__game_stockfish_skill_lvl = self.__stockfish_skill_level
        self.__game_duration = timedelta()
        # "UCI_LimitStrength": "true", "UCI_Elo": "1320",
        self.__board = Board()
        self.__chess_board_svg.src = svg.board(self.__board)
        while self.__game_status and not self.__board.is_game_over():
            engine_move: Move | None = self.__engine.play(self.__board, Limit(time=0.1)).move
            if engine_move is None or engine_move not in self.__board.legal_moves:
                self.logger(MessageType.ERROR, "No move found!")
                continue
            if self.__game_status:
                self.__board.push(engine_move)
                self.logger(MessageType.MOVE, f"Engine: {engine_move.uci()}")
                robot_move_from = self.robot.calculate_chessboard_point_to_move(engine_move.uci()[:2], 80)
                robot_move_to = self.robot.calculate_chessboard_point_to_move(engine_move.uci()[2:], 80)
                program: str = f"""SPEED 50 ALWAYS\nHMOVE #{robot_move_from.name}\nLDEPART -80\nLDEPART 80\nHMOVE #{robot_move_to.name}\nLDEPART -80\nLDEPART 80\n"""
                print(program)
                self.robot.write_program(program, "chess_move2")
                time.sleep(1)
                self.robot.send_command(RobotCommand.EXECUTE_PROG, "chess_move2")
                # self.robot.send_command(RobotCommand.MOVE_TO_POINT, robot_move_from)
                # while self.robot.get_robot_status()[RobotStatus.BUSY]:
                #     time.sleep(1)
                # self.robot.send_command(RobotCommand.PUTDOWN)
                # while self.robot.get_robot_status()[RobotStatus.BUSY]:
                #     time.sleep(1)
                # self.robot.send_command(RobotCommand.PICKUP)
                # while self.robot.get_robot_status()[RobotStatus.BUSY]:
                #     time.sleep(1)
                # self.robot.send_command(RobotCommand.MOVE_TO_POINT, robot_move_to)
                # while self.robot.get_robot_status()[RobotStatus.BUSY]:
                #     time.sleep(1)
                # self.robot.send_command(RobotCommand.PUTDOWN)
                # while self.robot.get_robot_status()[RobotStatus.BUSY]:
                #     time.sleep(1)
                # self.robot.send_command(RobotCommand.PICKUP)
                # while self.robot.get_robot_status()[RobotStatus.BUSY]:
                #     time.sleep(1)
                self.__chess_board_svg.src = svg.board(self.__board)
                self.__page.update()
        self.stop_game()
        if self.__board.is_game_over():
            self.database.add_game_data(
                self.__board,
                self.__start_datetime,
                self.__game_duration,
                self.__game_stockfish_skill_lvl,
                ("Stockfish", self.__player_name),
            )
            self.logger(MessageType.INFO, "Game data saved to database!")

    def stop_game(self) -> None:
        if not self.__game_status:
            return
        self.__game_status = False
        self.__engine.quit()
        self.robot.send_command(RobotCommand.HOME)
        self.logger(MessageType.GAME_STATUS, "Game stopped!")
        self.__page.update()

    def resign_game(self) -> None:
        if not self.__game_status:
            return
        self.__game_status = False
        self.__engine.quit()
        self.logger(MessageType.GAME_STATUS, "Game stopped! Player resigned!")
        self.__page.update()


class ChessApp:
    def __init__(self, page: Page) -> None:
        self.__board_height: Final[int] = 500
        self.__board_width: Final[int] = 500
        self.__app_padding: Final[int] = 20
        self.__page: Page = page
        self.__page.title = "ChessApp for Kawasaki"
        self.logger = Logger(self.__board_width * 2)
        self.database = ChessDatabase("chess.db")
        self.game_logic = GameLogic(self.__board_width, self.__board_height, self.logger, self.database, self.__page)
        self.__page.window.alignment = alignment.center
        self.__page.window.height = 900
        self.__maximize_button: IconButton = IconButton(
            icons.CHECK_BOX_OUTLINE_BLANK,
            on_click=lambda _: self.__maximize(),
            icon_size=15,
            selected=False,
            selected_icon=icons.COPY_OUTLINED,
            hover_color=colors.BLUE_400,
            style=ButtonStyle(shape=RoundedRectangleBorder(radius=5)),
        )
        self.__minimize_button: IconButton = IconButton(
            icons.MINIMIZE,
            on_click=lambda _: self.__minimize(),
            icon_size=15,
            hover_color=colors.GREEN_400,
            style=ButtonStyle(shape=RoundedRectangleBorder(radius=5)),
        )
        self.__close_button: IconButton = IconButton(
            icons.CLOSE,
            on_click=lambda _: self.__close(),
            icon_size=15,
            hover_color=colors.RED_400,
            style=ButtonStyle(shape=RoundedRectangleBorder(radius=5)),
        )
        self.__page.window.title_bar_hidden = True
        self.__page.window.on_event = self.__window_event
        self.__appbar = AppBar(
            toolbar_height=45,
            title=WindowDragArea(
                Row(
                    [
                        Text(self.__page.title, color="white", overflow=TextOverflow.ELLIPSIS, expand=True),
                    ],
                ),
                expand=True,
                maximizable=True,
            ),
            bgcolor=colors.GREY_900,
            title_spacing=self.__app_padding,
            actions=[
                self.__minimize_button,
                self.__maximize_button,
                self.__close_button,
                Container(width=20),
            ],
        )

        def on_slider_change(e: ControlEvent) -> None:
            self.game_logic.stockfish_skill_level = e.control.value
            page.update()

        def on_text_field_change(e: ControlEvent) -> None:
            self.game_logic.player_name = e.control.value
            page.update()

        self.__settings_tab = Column(
            [
                Text("Player nickname:", size=25, weight=FontWeight.BOLD),
                TextField(width=400, on_change=on_text_field_change, text_align=TextAlign.CENTER),
                Text("Stockfish skill level:", size=25, weight=FontWeight.BOLD),
                Slider(
                    min=1,
                    max=20,
                    divisions=19,
                    on_change=on_slider_change,
                    width=400,
                    value=self.game_logic.stockfish_skill_level,
                    label="{value}",
                ),
            ],
            horizontal_alignment=CrossAxisAlignment.CENTER,
            alignment=MainAxisAlignment.CENTER,
        )

        self.__about_tab = Container(content=Text("About tab", size=30, weight=FontWeight.BOLD), alignment=alignment.center)
        self.__logs_tab: ListView = self.logger.log_container
        self.__database_tab = Container()
        self.__clock = Text("0:00:00", size=60, weight=FontWeight.BOLD)

        def refresh() -> None:
            if not self.game_logic.game_status:
                return
            self.__clock.value = str(self.game_logic.game_duration)
            self.game_logic.game_duration += timedelta(seconds=1)
            self.__page.update()

        self.__timer: Timer = Timer(name="Clock", interval_s=1, callback=refresh)
        self.__game_tab = Container(
            Column(
                [
                    Row(
                        [
                            self.__timer,
                            self.__clock,
                        ],
                        alignment=MainAxisAlignment.CENTER,
                    ),
                    Row(
                        [
                            self.game_logic.chess_board_svg,
                            OpenCVCapture(self.__board_width, self.__board_height),
                        ],
                        alignment=MainAxisAlignment.CENTER,
                    ),
                    Row(
                        [
                            TextButton("Start", on_click=lambda _: self.game_logic.start_game(), icon=icons.PLAY_ARROW),
                            TextButton("Stop", on_click=lambda _: self.game_logic.stop_game(), icon=icons.STOP_SHARP),
                            TextButton("Resign", on_click=lambda _: self.game_logic.resign_game(), icon=icons.HANDSHAKE),
                            TextButton("Clear logs", on_click=lambda _: self.logger.clear(), icon=icons.CLEAR_ALL),
                        ],
                        alignment=MainAxisAlignment.CENTER,
                    ),
                ],
                horizontal_alignment=CrossAxisAlignment.CENTER,
                alignment=MainAxisAlignment.CENTER,
            ),
        )
        self.__tabs_layout: Tabs = Tabs(
            tabs=[
                Tab(text="Game", content=self.__game_tab, icon=icons.PLAY_ARROW),
                Tab(text="Settings", content=self.__settings_tab, icon=icons.SETTINGS),
                Tab(text="Logs", content=self.__logs_tab, icon=icons.RECEIPT_LONG),
                Tab(text="Database", content=self.__database_tab, icon=icons.STACKED_LINE_CHART),
                Tab(text="About", content=self.__about_tab, icon=icons.INFO_OUTLINED),
            ],
            expand=1,
            tab_alignment=TabAlignment.CENTER,
        )
        self.__page.add(self.__appbar, self.__tabs_layout)
        self.__page.update()

    def __close(self) -> None:
        self.game_logic.stop_game()
        self.database.close()
        self.__page.window.close()

    def __minimize(self) -> None:
        self.__page.window.minimized = True
        self.__page.update()

    def __maximize(self) -> None:
        self.__page.window.maximized = not self.__page.window.maximized
        self.__page.update()

    def __window_event(self, e: ControlEvent) -> None:
        if e.data in {"unmaximize", "maximize"}:
            self.__maximize_button.selected = self.__page.window.maximized
            self.__page.update()


if __name__ == "__main__":
    app(target=ChessApp)
    cv2.destroyAllWindows()
