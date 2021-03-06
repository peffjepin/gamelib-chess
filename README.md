# gamelib-chess
A chess application written as an example usage for gamelib.

![Screenshot](chess/assets/app-screenshot.png)

### Installation

Optionally create a virtual environment:

Linux:

```sh
python3 -m venv venv
. venv/bin/activate
```

Windows:

```cmd
python3 -m venv venv
venv\Scripts\activate
```

Clone the repository and install requirements:

```sh
git clone https://github.com/peffjepin/gamelib-chess.git
cd gamelib-chess
python3 -m pip install .
```


### Running the program:

After cloning the repo and installing requirements:

```sh
# console entry point should be available on Linux
play-chess

# I can't find any documentation about how the console entry points work
# on windows, but you can just run the main script.
python3 chess/main.py
```

You can launch in debug if you want to move the pieces for both sides to test things out.

```sh
play-chess -d
python main.py -d
```


### Controls

Click first on the piece you want to move, then on the square to move it to. There will be visual aids.
To clear your selected piece just click anywhere thats not shown as a valid move.

Esc closes the window. 
