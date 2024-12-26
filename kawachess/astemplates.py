from chess import Color

from kawachess.robot import Point, Program


def move_without_capture(from_point: Point, to_point: Point, drop: Point, speed: int, height: int) -> Program:
    return Program(
        f"""
        .PROGRAM kawachess_1 ()
            SPEED {speed} ALWAYS
            LMOVE {from_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {to_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {drop.name}
        .END

        """)


def move_with_capture(from_point: Point, to_point: Point, drop: Point, speed: int, height: int) -> Program:
    return Program(
        f"""
        .PROGRAM kawachess_2 ()
            SPEED {speed} ALWAYS
            LMOVE {to_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {drop.name}
            LMOVE {from_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {to_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {drop.name}
        .END

        """)


def kingside_castling(drop: Point, color: Color, speed: int, height: int) -> Program:
    # WHITE KING: E1->G1 ROOK: H1->F1
    # BLACK KING: E8->G8 ROOK: H8->F8
    return Program(
        f"""
        .PROGRAM kawachess_3 ()
            SPEED {speed} ALWAYS
            LMOVE {"E1" if color else "E8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {"G1" if color else "G8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {"H1" if color else "H8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {"F1" if color else "F8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {drop.name}
        .END

        """)


def queenside_castling(drop: Point, color: Color, speed: int, height: int) -> Program:
    # WHITE KING: E1->C1 ROOK: A1->D1
    # BLACK KING: E8->C8 ROOK: A8->D8
    return Program(
        f"""
        .PROGRAM kawachess_4 ()
            SPEED {speed} ALWAYS
            LMOVE {"E1" if color else "E8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {"C1" if color else "C8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {"A1" if color else "A8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {"D1" if color else "D8"}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {drop.name}
        .END

        """)


def en_passant(from_point: Point, to_point: Point, take_point: Point, drop: Point, speed: int, height: int) -> Program:
    return Program(
        f"""
        .PROGRAM kawachess_5 ()
            SPEED {speed} ALWAYS
            LMOVE {from_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {to_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {take_point.name}
            LDEPART -{height}
            LDEPART {height}
            LMOVE {drop.name}
        .END

        """)
