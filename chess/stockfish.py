import multiprocessing
import subprocess
import os
import pathlib
import time

from chess import model

_POSIX = os.name == "posix"
_FILENAME = "stockfish" if _POSIX else "stockfish.exe"
CPU_CNT = int(multiprocessing.cpu_count() // 2)
PROJECT_ROOT = pathlib.Path(__file__).parent
FILES = "0abcdefgh"
PIECES = {
    "n": model.Knight,
    "q": model.Queen,
    "r": model.Rook,
    "b": model.Bishop,
}


class Stockfish:
    def __init__(self, elo=1000, depth=1):
        self._process = subprocess.Popen(
            PROJECT_ROOT / "stockfish" / _FILENAME,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.depth = depth
        self._cmd("setoption name UCI_LimitStrength value true")
        self._cmd(f"setoption name UCI_Elo value {elo}")
        self._cmd(f"setoption name Threads value {CPU_CNT}")

    def _cmd(self, strcmd):
        self._process.stdin.write((strcmd + "\n").encode("utf-8"))
        self._process.stdin.flush()

    def make_move(self, move):
        self._ready_check()
        strmove = (
            f"{FILES[move.initial_file]}{move.initial_rank}"
            f"{FILES[move.target_file]}{move.target_rank}"
        )

        if move.promotion:
            for k, v in PIECES.items():
                if v == move.promotion:
                    if move.target_rank == 8:
                        strmove += k.upper()
                    else:
                        strmove += k
                    break

        self._cmd(f"position fen {self._fen()} moves {strmove}")

    def get_best_move(self):
        self._ready_check()
        self._cmd(f"go depth {self.depth}")

        # looking for this in stdout
        # bestmove c7c5 ponder g1f3
        # might be a pawn promotion
        # c7c8n
        while True:
            line = self._readline()
            if line.startswith("bestmove"):
                strmove = line.split(" ")[1]
                break

        f1, r1, f2, r2, *p = strmove
        if p:
            promotion = PIECES[p[0]]
        else:
            promotion = None

        files = list(FILES)
        return model.Move(
            files.index(f1),
            int(r1),
            files.index(f2),
            int(r2),
            promotion=promotion,
        )

    def set_start_state(self):
        self._ready_check()
        self._cmd("position startpos")

    def kill(self):
        self._process.kill()

    def _readline(self):
        line = str(self._process.stdout.readline(), "utf-8").strip()
        return line

    def _ready_check(self):
        self._cmd("isready")
        ts = time.time()
        timeout = 5
        while True:
            if ts + timeout <= time.time():
                raise TimeoutError(
                    "couldn't get readyok response from stockfish"
                )
            line = self._readline()
            if line == "readyok":
                return

    def _fen(self):
        self._ready_check()
        self._cmd("d")

        # looking for this in stdout
        # Fen: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1
        while True:
            line = self._readline()
            if line.startswith("Fen:"):
                return line[4:].strip()
