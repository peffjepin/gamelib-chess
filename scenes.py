import time
import numpy as np
import model
import stockfish
import gamelib

CLEAR = (0.15, 0.1, 0.10, 0)

class SideSelectionScene:

    white_piece: model.King
    black_piece: model.King
    selected: model.Player

    def __init__(self):
        self.selected = None
        self.camera = gamelib.rendering.PerspectiveCamera(
            position=(0, 0, 2.4), direction=(1, 0, -0.75), fov_y=35
        )
        self.instructions = gamelib.rendering.Renderer(
            shader="pieces",
            instanced=("model", "player", "entity"),
            indices=model.King.model.indices,
            v_pos=model.King.model.vertices,
            v_norm=model.King.model.normals,
            entity=model.King.ids_proxy,
            selected=-1,
            player=model.King.info.proxy("player"),
            model=model.King.transform.proxy("model_matrix"),
        )
        self.schema = gamelib.InputSchema(
            ("mouse1", self.cast_ray), enable=False
        )

    def __enter__(self):
        self.selected = None
        self.white_piece = model.King.create(0, 0, model.Player.WHITE)
        self.black_piece = model.King.create(0, 0, model.Player.BLACK)
        self.white_piece.transform.position = (1.5, 0.5, -0.4)
        self.white_piece.transform.theta = 135
        self.black_piece.transform.position = (1.5, -0.5, -0.4)
        self.black_piece.transform.theta = -135
        self.schema.enable()
        self.camera.set_primary()
        return self

    def __exit__(self, *args):
        gamelib.ecs.Entity.clear()
        self.schema.disable()

    def cast_ray(self, _):
        ray = self.camera.cursor_to_ray()
        entity = gamelib.ecs.collisions.nearest_entity_hit(ray)
        self.selected = None if entity is None else entity.info.player

    def update(self):
        gamelib.clear(*CLEAR)
        self.instructions.render()
        gamelib.update()


class GameScene:

    board: model.Board
    schema: gamelib.InputSchema

    def __init__(self, player, board, debug=False):
        if player == model.Player.WHITE:
            self.camera = gamelib.rendering.PerspectiveCamera(
                (4.5, -3, 8.5), (0, 7, -8.5), fov_y=45
            )
        else:
            self.camera = gamelib.rendering.PerspectiveCamera(
                (4.5, 12, 8.5), (0, -7, -8.5), fov_y=45
            )
        self.player = player
        if not debug:
            opponent = StockfishOpponent(model.Player.other(player), board)
        else:
            opponent = DebugOpponent(
                model.Player.other(player), board, self.camera
            )
        self.opponent = opponent
        self.board = board
        self.selected = None
        self.game_over = False
        self._fade_opacity = 0
        self._fade_opacity_step = 0.01
        self._promotion_props = []
        self._promotion_pending = None

        cube = gamelib.geometry.Cube()
        gamelib.geometry.Transform(
            scale=(9, 9, model.Board.VISUAL_DEPTH)
        ).apply(cube)
        cube.anchor((0, 0, 1))
        self.board_instructions = gamelib.rendering.Renderer(
            shader="board",
            v_pos=cube.triangles,
        )

        quad = gamelib.geometry.GridMesh()
        quad.anchor((0, 0, 0))
        self.hovered = np.array([(-1, -1)], gamelib.gl.ivec2)
        self.overlay_instructions = gamelib.rendering.Renderer(
            shader="overlay",
            instanced=("i_board", "i_capture"),
            v_pos=quad.triangles,
            hovered=self.hovered,
        )

        self._selected_id = np.array([-1])
        self.piece_instructions = []
        for p in model.Piece.__subclasses__():
            inst = gamelib.rendering.Renderer(
                shader="pieces",
                instanced=("model", "player", "entity"),
                selected=self._selected_id,
                v_pos=p.model.vertices,
                v_norm=p.model.normals,
                indices=p.model.indices,
                entity=p.ids_proxy,
                model=p.transform.proxy("model_matrix"),
                player=p.info.proxy("player"),
            )
            self.piece_instructions.append(inst)

        self.fade_out_instructions = gamelib.rendering.Renderer(
            "fade",
            v_pos=[(-1, -1), (-1, 1), (1, 1), (-1, -1), (1, 1), (1, -1)]
        )

        self.schema = gamelib.InputSchema(
            ("mouse1", self.cast_ray),
            enable=False,
        )

    def __enter__(self):
        self.selected = None
        self.camera.set_primary()
        self.schema.enable()
        return self

    def __exit__(self, *args):
        gamelib.ecs.Entity.clear()
        self.opponent.cleanup()
        self.schema.disable()

    def cast_ray(self, _):
        if self.board.winner is not None:
            return
        if not self.board.is_turn(self.player):
            return
        if self._promotion_pending:
            self._handle_promotion_pending()
            return

        if self.selected is None:
            self.select_piece()
        else:
            file, rank = self.hovered[0]
            self.request_move(file, rank)
            self.selected = None

    def _handle_promotion_pending(self):
        self.select_piece()

        if self.selected not in self._promotion_props:
            self.selected = None
            return

        self._promotion_pending.promotion = type(self.selected)
        for piece in self._promotion_props:
            gamelib.ecs.Entity.destroy(piece.id)
        self._promotion_props = []
        self.board.make_move(self._promotion_pending)
        self._promotion_pending = None
        self.selected = None

    def request_move(self, file, rank):
        ifile, irank = (
            self.selected.info.file,
            self.selected.info.rank,
        )
        move = None
        for m in self.selected.possible_moves(self.board):
            if (
                m.initial_file == ifile
                and m.initial_rank == irank
                and m.target_file == file
                and m.target_rank == rank
            ):
                move = m
        if not move:
            return
        if self.board.is_promotion(move):
            self._promotion_pending = move
            self.init_promotion_selection()
            return
        self.board.make_move(move)

    def update_hovered(self):
        ray = self.camera.cursor_to_ray()
        self.hovered[:] = model.ray_to_file_and_rank(ray)

    def select_piece(self):
        ray = self.camera.cursor_to_ray()
        entity = gamelib.ecs.collisions.nearest_entity_hit(ray)

        if entity is not None and entity.info.player == self.player:
            self.selected = entity
        else:
            self.selected = None

    def update(self):
        gamelib.clear(*CLEAR)
        self.board_instructions.render()
        for inst in self.piece_instructions:
            inst.render()

        if self.board.winner is not None:
            self.fade_out()
        else:
            self.write_overlay_buffers()
            self.overlay_instructions.render()
            self.opponent.handle_turn()
            self.update_hovered()

        gamelib.update()

    def fade_out(self):
        self.fade_out_instructions.source(opacity=self._fade_opacity)
        self.fade_out_instructions.render()
        self._fade_opacity += self._fade_opacity_step
        if self._fade_opacity >= 1.0:
            self.game_over = True

    def write_overlay_buffers(self):
        if not self.selected and not self.opponent.selected:
            moves = []
        else:
            selected = self.selected or self.opponent.selected
            moves = list(selected.possible_moves(self.board))
        i_board = [(m.target_file, m.target_rank) for m in moves]
        i_capture = [0 if m.capture is None else 1 for m in moves]
        if not self.board.previous_move:
            prev_move = (-1, -1)
        else:
            prev_move = (
                self.board.previous_move.target_file,
                self.board.previous_move.target_rank,
            )
            i_board.append(prev_move)
            i_capture.append(0)

        self.overlay_instructions.source(
            i_board=i_board,
            i_capture=i_capture,
            prev_move=prev_move,
        )

    def init_promotion_selection(self):
        pfile = self._promotion_pending.target_file
        prank = self._promotion_pending.target_rank
        prop_rank = 9 if prank == 8 else 0
        player = self.board.piece_at(
            self._promotion_pending.initial_file,
            self._promotion_pending.initial_rank,
        ).info.player

        self._promotion_props = [
            model.Queen.create(pfile, prop_rank, player),
            model.Knight.create(pfile - 1, prop_rank, player),
            model.Bishop.create(pfile + 1, prop_rank, player),
            model.Rook.create(pfile - 2, prop_rank, player),
        ]
        for piece in self._promotion_props:
            piece.transform.position += (0, 0, 0.25)
            piece.transform.theta += 180


class LoadingScene:
    def __init__(self):
        n = 50
        self.instructions = gamelib.rendering.Renderer(
            shader="loading",
            v_pos=[((i / n * 2) - 1, -0.8) for i in range(n + 1)],
            mode=gamelib.gl.POINTS,
        )
        self.done_loading = False

    def __enter__(self):
        gamelib.get_context().point_size = 3
        gamelib.threaded_schedule.once(self.load, -1)
        return self

    def __exit__(self, *args):
        pass

    def load(self):
        model.init_geometry()
        self.done_loading = True

    def update(self):
        gamelib.clear(*CLEAR)
        self.instructions.render()
        gamelib.update()


class Opponent:

    selected = None

    def __init__(self, player: model.Player, board: model.Board):
        self.player = player
        self.board = board
        self.thinking = False
        self.move = None

    def calculate_move(self):
        raise NotImplementedError()

    def think(self):
        self.move = self.calculate_move()

    def handle_turn(self):
        if self.board.is_turn(self.player):
            if not self.thinking:
                self.move = None
                self.thinking = True
                gamelib.threaded_schedule.once(self.think, -1)
            else:
                if self.move is not None:
                    self.board.make_move(self.move)
                    self.move = None
                    self.thinking = False

    def cleanup(self):
        # optional cleanup hook at scene exit
        pass


class StockfishOpponent(Opponent):

    sf = stockfish.Stockfish(elo=1, depth=1)

    def __init__(self, player, board):
        super().__init__(player, board)
        self.sf.set_start_state()

    def calculate_move(self):
        prev_move = self.board.previous_move
        if prev_move is not None:
            self.sf.make_move(prev_move)

        move = self.sf.get_best_move()
        self.sf.make_move(move)
        return move


class DebugOpponent(Opponent):
    def __init__(self, player, board, camera):
        super().__init__(player, board)
        self.selected = None
        self._move = None
        self._camera = camera
        self._schema = gamelib.InputSchema(
            ("mouse1", self.cast_ray), enable=False
        )

    def cast_ray(self, _):
        ray = self._camera.cursor_to_ray()

        if self.selected is None:
            entity = gamelib.ecs.collisions.nearest_entity_hit(ray)
            if entity is not None and entity.info.player == self.player:
                self.selected = entity
        else:
            self._move = self.get_move(*model.ray_to_file_and_rank(ray))
            self.selected = None

    def get_move(self, file, rank):
        ifile, irank = (
            self.selected.info.file,
            self.selected.info.rank,
        )
        move = None
        for m in self.selected.possible_moves(self.board):
            if (
                m.initial_file == ifile
                and m.initial_rank == irank
                and m.target_file == file
                and m.target_rank == rank
            ):
                move = m
        if not move:
            return
        if self.board.is_promotion(move):
            move.promotion = model.Queen
        return move

    def calculate_move(self):
        self._schema.enable()
        while self._move is None:
            time.sleep(1 / gamelib.config.tps)
        move = self._move
        self._move = None
        self._schema.disable()
        return move

    def cleanup(self):
        self._schema.disable()
