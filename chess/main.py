import sys
import pathlib

import gamelib
from gamelib.core import resources

from chess import model
from chess import scenes


def main():
    debug = "-d" in sys.argv
    resources.set_content_roots(pathlib.Path(__file__).parent)
    gamelib.init(title="gamelib-chess")

    with scenes.LoadingScene() as scene:
        while not scene.done_loading:
            scene.update()


    side_selection = scenes.SideSelectionScene()


    while gamelib.is_running():

        with side_selection as scene:
            while scene.selected is None:
                scene.update()

        player = scene.selected
        board = model.Board(player)
        game_scene = scenes.GameScene(player, board, debug)

        with game_scene as scene:
            while not scene.game_over:
                scene.update()


if __name__ == "__main__":
    main()
