.PROGRAM kawachess_1 (.arg1, .arg2)
    SPEED 5 ALWAYS
    LMOVE .arg2
    LDEPART -80
    LDEPART 80
    LMOVE drop_point
    LDEPART -80
    LDEPART 80
    LMOVE .arg1
    LDEPART -80
    LDEPART 80
    LMOVE .arg2
    LDEPART -80
    LDEPART 80
    LMOVE drop_point
.END

.PROGRAM kawachess_2 (.arg1, .arg2)
    SPEED 5 ALWAYS
    LMOVE .arg2
    LDEPART -80
    LDEPART 80
    LMOVE drop_point
    LDEPART -80
    LDEPART 80
    LMOVE .arg1
    LDEPART -80
    LDEPART 80
    LMOVE .arg2
    LDEPART -80
    LDEPART 80
    LMOVE drop_point
.END

.PROGRAM test ()
    SPEED 5 ALWAYS
    HOME
.END
