from chess import Color

from kawachess.gripper import State as Gripper
from kawachess.robot import Point, Program


def home(speed: int, height: int, drop: Point) -> Program:
    return Program(
        f"""
        .PROGRAM homie ()
        SPEED {speed} ALWAYS
        LDEPART {height}
        LMOVE {drop.name}
        .END

        """
    )


def move_without_capture(from_point: Point, to_point: Point, drop: Point, speed: int, height: int) -> tuple[Program | Gripper, ...]:
    return (
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM nocap_1 ()
            SPEED {speed} ALWAYS
            LMOVE {from_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM nocap_2 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {to_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        home(30, height, drop),
    )


def move_with_capture(from_point: Point, to_point: Point, drop: Point, speed: int, height: int) -> tuple[Program | Gripper, ...]:
    return (
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM cap_1 ()
            SPEED {speed} ALWAYS
            LMOVE {to_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM cap_2 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {drop.name}
            .END

            """
        ),
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM cap_3 ()
            SPEED {speed} ALWAYS
            LMOVE {from_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM cap_4 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {to_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        home(30, height, drop),
    )


def kingside_castling(drop: Point, color: Color, speed: int, height: int) -> tuple[Program | Gripper, ...]:
    # WHITE KING: E1->G1 ROOK: H1->F1
    # BLACK KING: E8->G8 ROOK: H8->F8
    return (
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM king_1 ()
            SPEED {speed} ALWAYS
            LMOVE {"E1" if color else "E8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM king_2 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {"G1" if color else "G8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM king_3 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {"H1" if color else "H8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM king_4 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {"F1" if color else "F8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        home(30, height, drop),
    )


def queenside_castling(drop: Point, color: Color, speed: int, height: int) -> tuple[Program | Gripper, ...]:
    # WHITE KING: E1->C1 ROOK: A1->D1
    # BLACK KING: E8->C8 ROOK: A8->D8
    return (
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM queen_1 ()
            SPEED {speed} ALWAYS
            LMOVE {"E1" if color else "E8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM queen_2 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {"C1" if color else "C8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM queen_3 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {"A1" if color else "A8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM queen_4 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {"D1" if color else "D8"}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        home(30, height, drop),
    )


def en_passant(from_point: Point, to_point: Point, take_point: Point, drop: Point, speed: int, height: int) -> tuple[Program | Gripper, ...]:
    return (
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM enpass_1 ()
            SPEED {speed} ALWAYS
            LMOVE {from_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        Program(
            f"""
            .PROGRAM enpass_2 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {to_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.OPEN,
        Program(
            f"""
            .PROGRAM enpass_3 ()
            SPEED {speed} ALWAYS
            LDEPART {height}
            LMOVE {take_point.name}
            LDEPART -{height}
            .END

            """
        ),
        Gripper.CLOSE,
        home(30, height, drop),
        Gripper.OPEN,
    )
