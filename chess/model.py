import collections
import dataclasses
import enum
import math

from typing import Optional
from typing import Union
from typing import Generator
from typing import Iterable
from typing import List
from typing import Tuple
from typing import Type
from typing import Any

import gamelib


def init_geometry():
    # this is an expensive call, so it should be delegated to a thread
    # to avoid hanging the app while waiting for it to finish.

    for cls in Piece.__subclasses__():
        cls.model = gamelib.geometry.load_model(cls.__name__.lower())
        cls.model.anchor((0.5, 0.5, 0))
        cls.bvh = gamelib.geometry.BVH.create_tree(cls.model, cls.BVH_DENSITY)


class Player(enum.Enum):
    BLACK = 0
    WHITE = 1

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Player):
            return self.value == other
        else:
            return self.value == other.value

    @classmethod
    def other(cls, player: Union[int, "Player"]) -> "Player":
        if player == Player.WHITE:
            return Player.BLACK
        else:
            return Player.WHITE


class PieceInfo(gamelib.ecs.Component):
    player: int
    file: int
    rank: int
    prev_file: int
    prev_rank: int

    @classmethod
    def create(cls, player, file, rank, prev_rank=None, prev_file=None):
        return super().create(
            player=player,
            file=file,
            rank=rank,
            prev_rank=prev_rank or rank,
            prev_file=prev_file or file,
        )

    def __repr__(self):
        file = "abcdefgh"[self.file - 1]
        return f"{Player(self.player)}, {file}{self.rank}"


class Piece(gamelib.ecs.Entity):
    SCALE = (0.55, 0.55, 0.55)
    BVH_DENSITY = 512
    MODEL_ROTATION = 0

    # defined on subclasses
    initial_positions = None

    # populated with a call to init_geometry()
    model = None
    bvh = None

    # ecs components
    info: PieceInfo
    hitbox: gamelib.ecs.Hitbox
    transform: gamelib.ecs.Transform

    @classmethod
    def create(cls, file, rank, player):
        player = player if not isinstance(player, Player) else player.value
        info = PieceInfo.create(player, file, rank)
        hitbox = gamelib.ecs.Hitbox.create(cls.bvh, cls.BVH_DENSITY)
        theta = cls.MODEL_ROTATION
        if player == Player.BLACK:
            theta = -theta
        transform = gamelib.ecs.Transform.create(
            (file, rank, 0), cls.SCALE, theta=theta
        )
        return super().create(info=info, hitbox=hitbox, transform=transform)

    def __repr__(self):
        return f"<{self.__class__.__name__}(self.id={self.id}, {self.info!r})>"

    @property
    def has_moved(self) -> bool:
        return (
            self.info.rank != self.info.prev_rank
            or self.info.file != self.info.prev_file
        )

    def possible_moves(self, board: "Board") -> Generator:
        raise NotImplementedError("should be implemented in subclass")


@dataclasses.dataclass
class Move:
    initial_file: int
    initial_rank: int
    target_file: int
    target_rank: int
    capture: Optional[Piece] = None
    promotion: Optional[Type[Piece]] = None


class Board:
    VISUAL_DEPTH = 0.5

    _board: List[List[Optional[Piece]]]
    winner: Union[int, Player, None]  # -1 on draw

    def __init__(self, player) -> None:
        self.winner = None
        self.previous_move = None

        self._prev_positions = collections.defaultdict(int)
        self._player = player
        self._turn = Player.WHITE
        self._board = [[None] * 8 for _ in range(8)]
        self._init_entities()
        self._black_king = self.piece_at(5, 8)
        self._white_king = self.piece_at(5, 1)

    def __iter__(self) -> Iterable[Piece]:
        for rank in self._board:
            for piece in rank:
                if piece is not None:
                    yield piece

    def __repr__(self) -> str:
        lines = []
        letters = {
            Pawn: "p",
            Knight: "n",
            Bishop: "b",
            King: "k",
            Queen: "q",
            Rook: "r",
        }
        for rank in reversed(self._board):
            pieces = []
            for piece in rank:
                if piece is None:
                    rep = "."
                else:
                    letter = letters[type(piece)]
                    if piece.info.player == Player.WHITE:
                        rep = letter.upper()
                    else:
                        rep = letter
                rep = rep + " "
                pieces.append(rep)
            lines.append("".join(pieces))
        return "\n".join(lines)

    def __hash__(self):
        return hash(repr(self))

    def __eq__(self, other):
        return isinstance(other, Board) and repr(self) == repr(other)

    @property
    def last_piece_to_move(self):
        if self.previous_move is None:
            return None
        return self.piece_at(
            self.previous_move.target_file, self.previous_move.target_rank
        )

    @staticmethod
    def in_range(file: int, rank: int) -> bool:
        return (1 <= file <= 8) and (1 <= rank <= 8)

    def is_turn(self, player):
        return self._turn == player

    def is_empty(self, file: int, rank: int) -> bool:
        if not self.in_range(file, rank):
            return True
        return self._board[rank - 1][file - 1] is None

    def is_valid(self, move: Move) -> bool:
        init_piece = self.piece_at(move.initial_file, move.initial_rank)
        if init_piece is None:
            # nothing to move
            return False

        target_piece = self.piece_at(move.target_file, move.target_rank)
        player = init_piece.info.player
        if target_piece is not None and target_piece.info.player == player:
            # cant step on our own pieces
            return False

        self._logical_move(move)
        player_in_check = self.in_check(player)
        self._logical_unmove(move)
        return not player_in_check

    def is_promotion(self, move):
        piece = self.piece_at(move.initial_file, move.initial_rank)
        if not isinstance(piece, Pawn):
            return False

        player = piece.info.player
        promotion_rank = 8 if player == Player.WHITE else 1
        return move.target_rank == promotion_rank

    def in_check(self, player: Union[int, Player]) -> bool:
        if player == Player.BLACK:
            king = self._black_king
            other_player = Player.WHITE
        else:
            king = self._white_king
            other_player = Player.BLACK
        return self.is_controlled(king.info.file, king.info.rank, other_player)

    def piece_at(self, file: int, rank: int) -> Optional[Piece]:
        if not self.is_empty(file, rank):
            return self._board[rank - 1][file - 1]
        else:
            return None

    def is_controlled(
        self,
        file: int,
        rank: int,
        player: Union[int, Player],
    ) -> bool:
        # check if the square is controlled by a knight
        knight_hops = (
            (file - 2, rank - 1),
            (file - 2, rank + 1),
            (file - 1, rank - 2),
            (file - 1, rank + 2),
            (file + 1, rank + 2),
            (file + 1, rank - 2),
            (file + 2, rank + 1),
            (file + 2, rank - 1),
        )
        for f, r in knight_hops:
            piece = self.piece_at(f, r)
            if isinstance(piece, Knight) and piece.info.player == player:
                return True

        # check for diagonal control
        diags = ((-1, -1), (-1, 1), (1, -1), (1, 1))
        for dx, dy in diags:
            f, r = file + dx, rank + dy
            piece = None
            # go along diagonal until out of bounds or you hit another piece
            while self.in_range(f, r):
                piece = self.piece_at(f, r)
                if piece is not None:
                    break
                f += dx
                r += dy

            forward = 1 if player == Player.WHITE else -1
            possible_pieces = [Bishop, Queen]
            # check if King/Pawn could be controlling this diagonal
            if abs(f - file) == 1 and abs(r - rank) == 1:
                possible_pieces.append(King)
                if r == rank - forward:
                    possible_pieces.append(Pawn)

            if type(piece) in possible_pieces and piece.info.player == player:
                return True

        # check for control along files/ranks
        lines = ((0, 1), (0, -1), (1, 0), (-1, 0))
        for dx, dy in lines:
            f, r = file + dx, rank + dy
            piece = None
            # stop at first piece hit
            while self.in_range(f, r):
                piece = self.piece_at(f, r)
                if piece is not None:
                    break
                f += dx
                r += dy

            # check if king is in range
            if abs(f - file) <= 1 and abs(r - rank) <= 1:
                possible_pieces = (Rook, Queen, King)
            else:
                possible_pieces = (Queen, Rook)

            if type(piece) in possible_pieces and piece.info.player == player:
                return True

        return False

    def make_move(self, move: Move) -> None:
        self._logical_move(move)
        self._finalize_move(move)
        self._turn = Player.other(self._turn)
        self.previous_move = move

    def _logical_move(self, move: Move) -> None:
        # check for normal capture
        capture = self.piece_at(move.target_file, move.target_rank)
        if capture is not None:
            move.capture = capture
        # capture can also be set from en_passent rule so these checks should
        # not be combined
        if move.capture is not None:
            ri, fi = move.capture.info.rank - 1, move.capture.info.file - 1
            self._board[ri][fi] = None

        if self._is_castles(move):
            rook_move = self._get_castles_rook_move(move)
            self._logical_move(rook_move)

        piece = self.piece_at(move.initial_file, move.initial_rank)
        piece.info.file = move.target_file
        piece.info.rank = move.target_rank
        self._swap(
            move.initial_file,
            move.initial_rank,
            move.target_file,
            move.target_rank,
        )

    def _logical_unmove(self, move: Move) -> None:
        inverse_move = Move(
            move.target_file,
            move.target_rank,
            move.initial_file,
            move.initial_rank,
        )
        self._logical_move(inverse_move)

        if self._is_castles(move):
            rook_move = self._get_castles_rook_move(move)
            self._logical_unmove(rook_move)

        if move.capture is not None:
            ri, fi = move.capture.info.rank - 1, move.capture.info.file - 1
            self._board[ri][fi] = move.capture

    def _finalize_move(self, move: Move) -> None:
        if move.capture:
            Piece.destroy(move.capture.id)

        if self._is_finalize_castles(move):
            rook_move = self._get_castles_rook_move(move)
            self._finalize_move(rook_move)

        piece = self.piece_at(move.target_file, move.target_rank)
        piece.info.prev_file = move.initial_file
        piece.info.prev_rank = move.initial_rank
        piece.transform.position = (move.target_file, move.target_rank, 0)

        if move.promotion is not None:
            self._handle_promotion(move)

        self._handle_end_state()

    def _swap(self, file1: int, rank1: int, file2: int, rank2: int) -> None:
        r1, r2, f1, f2 = rank1 - 1, rank2 - 1, file1 - 1, file2 - 1
        self._board[r1][f1], self._board[r2][f2] = (
            self._board[r2][f2],
            self._board[r1][f1],
        )

    def _is_castles(self, move: Move) -> bool:
        return (
            isinstance(
                self.piece_at(move.initial_file, move.initial_rank), King
            )
            and abs(move.initial_file - move.target_file) == 2
            and move.initial_file == 5
        )

    def _is_finalize_castles(self, move: Move) -> bool:
        return (
            isinstance(self.piece_at(move.target_file, move.target_rank), King)
            and abs(move.initial_file - move.target_file) == 2
            and move.initial_file == 5
        )

    @staticmethod
    def _get_castles_rook_move(move: Move) -> Move:
        if move.target_file == 3:
            initial_file = 1
            target_file = 4
        else:
            initial_file = 8
            target_file = 6

        move = Move(
            initial_file, move.initial_rank, target_file, move.target_rank
        )
        return move

    def _handle_promotion(self, move: Move) -> None:
        piece = self.piece_at(move.target_file, move.target_rank)
        player = piece.info.player
        Piece.destroy(piece.id)

        promotion_rank = 8 if player == Player.WHITE else 1
        promotion_type = move.promotion
        promoted_piece = promotion_type.create(
            move.target_file, promotion_rank, player
        )
        self._board[promotion_rank - 1][move.target_file - 1] = promoted_piece

    def _handle_end_state(self) -> None:
        self._handle_drawn_by_repitition()
        if self.winner is not None:
            return

        self._handle_checkmate()
        if self.winner is not None:
            return

        self._handle_insufficient_material()

    def _handle_checkmate(self):
        victim = Player.other(self._turn)
        drawn = not self.in_check(victim)

        # look for possible moves
        for piece in self:
            if piece.info.player == victim:
                if next(piece.possible_moves(self), None):
                    # possible move found, end condition not met.
                    return

        # no possible moves found, game must be over
        self.winner = -1 if drawn else self._turn

    def _handle_drawn_by_repitition(self):
        key = hash(self)
        self._prev_positions[key] += 1
        if self._prev_positions[key] >= 3:
            self.winner = -1

    def _handle_insufficient_material(self):
        # not drawn cases
        if len(Pawn) > 0 or len(Rook) > 0 or len(Queen) > 0:
            return
        if len(Bishop) + len(Knight) > 2:
            return

        # we will consider a game drawn by insufficient material when both
        # sides are down to just their king and a minor piece or less and no
        # pawns are on the board.

        # definitely drawn
        if len(Bishop) + len(Knight) == 1:
            self.winner = -1
            return

        # need to check who the pieces belong to.
        if len(Bishop) == 2:
            p1, p2 = Bishop
        elif len(Knight) == 2:
            p1, p2 = Knight
        else:
            p1, p2 = next(iter(Bishop)), next(iter(Knight))
        if p1.info.player != p2.info.player:
            self.winner = -1

    def _init_entities(self) -> None:
        for entity in Piece.__subclasses__():
            for file, rank in entity.initial_positions:
                entity_w = entity.create(file, rank, Player.WHITE)
                self._board[rank - 1][file - 1] = entity_w

                entity_b = entity.create(file, 9 - rank, Player.BLACK)
                self._board[8 - rank][file - 1] = entity_b


class Pawn(Piece):
    initial_positions = tuple((file + 1, 2) for file in range(8))

    def possible_moves(self, board):
        file, rank = self.info.file, self.info.rank
        player = self.info.player
        forward = 1 if player == Player.WHITE.value else -1

        if board.is_empty(file, rank + forward):
            move = Move(file, rank, file, rank + forward)
            if board.is_valid(move):
                yield move

            if not self.has_moved and board.is_empty(file, rank + 2 * forward):
                move = Move(file, rank, file, rank + 2 * forward)
                if board.is_valid(move):
                    yield move

        for dx in (-1, 1):
            normal_capture = board.piece_at(file + dx, rank + forward)
            if (
                normal_capture is not None
                and normal_capture.info.player != player
            ):
                move = Move(
                    file, rank, file + dx, rank + forward, normal_capture
                )
                if board.is_valid(move):
                    yield move

            en_passant = board.piece_at(file + dx, rank)
            if (
                en_passant is not None
                and isinstance(en_passant, Pawn)
                and en_passant == board.last_piece_to_move
                and en_passant.info.player != player
                # fmt: off
                and abs(en_passant.info.rank - en_passant.info.prev_rank) == 2
                # fmt: on
            ):
                move = Move(file, rank, file + dx, rank + forward, en_passant)
                if board.is_valid(move):
                    yield move


class Knight(Piece):
    MODEL_ROTATION = 90
    initial_positions = ((2, 1), (7, 1))

    def possible_moves(self, board):
        rank, file = self.info.rank, self.info.file

        for dx, dy in (
            (-2, -1),
            (-2, 1),
            (-1, -2),
            (-1, 2),
            (1, 2),
            (1, -2),
            (2, 1),
            (2, -1),
        ):
            f, r = file + dx, rank + dy
            if not board.in_range(f, r):
                continue

            move = Move(file, rank, f, r)
            if board.is_valid(move):
                yield move


class Bishop(Piece):
    initial_positions = ((3, 1), (6, 1))

    def possible_moves(self, board):
        rank, file = self.info.rank, self.info.file
        dirs = ((-1, -1), (-1, 1), (1, -1), (1, 1))

        for dx, dy in dirs:
            f, r = file + dx, rank + dy
            while board.in_range(f, r):
                piece = board.piece_at(f, r)
                move = Move(file, rank, f, r)
                if board.is_valid(move):
                    yield move
                if piece is not None:
                    break
                f += dx
                r += dy


class Rook(Piece):
    initial_positions = ((1, 1), (8, 1))

    def possible_moves(self, board):
        rank, file = self.info.rank, self.info.file
        dirs = ((0, -1), (0, 1), (1, 0), (-1, 0))

        for dx, dy in dirs:
            f, r = file + dx, rank + dy
            while board.in_range(f, r):
                piece = board.piece_at(f, r)
                move = Move(file, rank, f, r)
                if board.is_valid(move):
                    yield move
                if piece is not None:
                    break
                f += dx
                r += dy


class Queen(Piece):
    initial_positions = ((4, 1),)

    def possible_moves(self, board):
        rank, file = self.info.rank, self.info.file
        dirs = (
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
            (0, -1),
            (0, 1),
            (1, 0),
            (-1, 0),
        )

        for dx, dy in dirs:
            f, r = file + dx, rank + dy
            while board.in_range(f, r):
                piece = board.piece_at(f, r)
                move = Move(file, rank, f, r)
                if board.is_valid(move):
                    yield move
                if piece is not None:
                    break
                f += dx
                r += dy


class King(Piece):
    initial_positions = ((5, 1),)

    def possible_moves(self, board):
        rank, file = self.info.rank, self.info.file
        player = self.info.player
        other_player = Player.other(player)
        dirs = (
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
            (0, -1),
            (0, 1),
            (1, 0),
            (-1, 0),
        )

        # standard moves
        for dx, dy in dirs:
            f, r = file + dx, rank + dy
            if not board.in_range(f, r):
                continue
            move = Move(file, rank, f, r)
            if board.is_valid(move):
                yield move

        if self.has_moved:
            return

        # castling
        for corner in (1, 8):
            rook = board.piece_at(corner, rank)
            dx = -1 if corner == 1 else 1
            rook_destination_file = file + dx
            if (
                # we need a rook in the corner that hasnt yet moved
                isinstance(rook, Rook)
                and rook.info.player == player
                and not rook.has_moved
                # we cant be in check or step through check
                and not board.in_check(player)
                and not board.is_controlled(
                    rook_destination_file, rank, other_player
                )
                # the rooks square must be empty
                and board.is_empty(rook_destination_file, rank)
            ):
                move = Move(file, rank, file + 2 * dx, rank)
                if board.is_valid(move):
                    # not castling into check implied here
                    yield move


def ray_to_file_and_rank(ray: gamelib.geometry.Ray) -> Tuple[int, int]:
    t = abs(ray.origin.z / ray.direction.z)
    on_plane = ray.origin + ray.direction * t
    file = int(math.ceil(on_plane.x - 0.5))
    rank = int(math.ceil(on_plane.y - 0.5))
    return file, rank
