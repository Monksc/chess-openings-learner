import random
import requests
import chess
import chess.pgn
from stockfish import Stockfish
import io
import json
import tkinter as tk

BOARD_SIZE = 480
SQUARE = BOARD_SIZE // 8

PIECE_IMAGES = {}
PIECES = {
    "p": "♟", "r": "♜", "n": "♞", "b": "♝", "q": "♛", "k": "♚",
    "P": "♙", "R": "♖", "N": "♘", "B": "♗", "Q": "♕", "K": "♔"
}

class ChessGUI:
    def __init__(self, fen=None, stockfish=None):
        self.window = tk.Tk()
        self.window.title("Python Chess GUI")

        self.canvas = tk.Canvas(self.window, width=BOARD_SIZE, height=BOARD_SIZE)
        self.canvas.pack()

        if fen is None:
            self.board = chess.Board()
        else:
            self.board = chess.Board(fen)

        self.selected = None
        self.should_remove_move = False
        self.stockfish = stockfish

        self.draw_board()
        self.draw_pieces()

        self.canvas.bind("<Button-1>", self.on_click)

    def draw_board(self):
        self.canvas.delete("square")
        color = "#EEE"

        for r in range(8):
            for c in range(8):
                x1 = c * SQUARE
                y1 = r * SQUARE
                x2 = x1 + SQUARE
                y2 = y1 + SQUARE
                fill = "#EEE" if (r + c) % 2 == 0 else "#999"
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, tags="square")

    def draw_pieces(self):
        self.canvas.delete("piece")

        for square, piece_obj in self.board.piece_map().items():
            r = 7 - chess.square_rank(square)
            c = chess.square_file(square)

            piece = piece_obj.symbol()
            text = PIECES[piece]

            x = c * SQUARE + SQUARE//2
            y = r * SQUARE + SQUARE//2

            self.canvas.create_text(x, y, text=text, font=("Arial", 32), tags="piece")

    def on_click(self, event):
        c = event.x // SQUARE
        r = event.y // SQUARE
        square = chess.square(c, 7 - r)

        if self.should_remove_move:
            self.board.pop()
            self.draw_board()
            self.draw_pieces()
            self.should_remove_move = False
            return

        if self.selected is None:
            # First click: select piece
            if self.board.piece_at(square):
                self.selected = square
        else:
            # Second click: try a move
            move = chess.Move(self.selected, square)
            print("Tried Move: ", move)
            if move in self.board.legal_moves:
                print("Is legal")
                #Get engine's top move in UCI format
                self.stockfish.set_fen_position(self.board.fen())
                top_move_uci = self.stockfish.get_best_move()
                top_move = chess.Move.from_uci(top_move_uci)

                if move == top_move:
                    print("Correct Move")
                    self.board.push(top_move)
                    self.draw_board()
                    self.draw_pieces()
                else:

                    # Convert evals to centipawns
                    def cp(e):
                        if e["type"] == "mate":
                            return 100000 if e["value"] > 0 else -100000
                        return e["value"]

                    before_eval = engine.get_evaluation()
                    self.board.push(move)
                    self.stockfish.set_fen_position(self.board.fen())
                    after_eval = engine.get_evaluation()

                    cp_before = cp(before_eval)
                    cp_after = cp(after_eval)
                    delta = cp_after - cp_before

                    self.draw_board()
                    self.draw_pieces()

                    if abs(delta) < (100 * 1.5 * CENTI_PAWN_LOST / 2):
                        print("Good Enough ", move, square, " Top Move: ", top_move, top_move.from_square)
                        print("Move quality: ", delta, " Went from", cp_before, "to", cp_after)
                    else:
                        self.should_remove_move = True
                        print("Wrong Move ", move, square, " Top Move: ", top_move, top_move.from_square)
                        print("Move quality: ", delta, " Went from", cp_before, "to", cp_after)

            self.selected = None

    def run(self):
        self.window.mainloop()


USERNAME = "monksc"
STOCKFISH_PATH = "/usr/games/stockfish"
GAME_COUNT = 4
PLIES = 14
CENTI_PAWN_LOST = 0.2
DEPTH = 20

# Set up Stockfish engine
engine = Stockfish(STOCKFISH_PATH)
engine.set_depth(DEPTH)

# Fetch games
url = f"https://lichess.org/api/games/user/{USERNAME}?max={GAME_COUNT}&analysed=1&pgnInJson=true"
headers = {"Accept": "application/x-ndjson"}

resp = requests.get(url, headers=headers, stream=True)
resp.raise_for_status()
print(resp)

mistakes = []

for line in resp.iter_lines():
    print("Line: ", line)
    if not line:
        continue

    game_json = json.loads(line)
    pgn_text = game_json["pgn"]

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    board = game.board()

    # Iterate through first 10 moves (20 plies)
    for ply, move in enumerate(game.mainline_moves(), start=1):
        if ply > PLIES:
            break

        fen_before = board.fen()
        san_move = board.san(move)

        # Engine eval before move
        engine.set_fen_position(fen_before)
        before_eval = engine.get_evaluation()

        board.push(move)
        fen_after = board.fen()

        # Engine eval after move
        engine.set_fen_position(fen_after)
        after_eval = engine.get_evaluation()

        # Convert evals to centipawns
        def cp(e):
            if e["type"] == "mate":
                return 100000 if e["value"] > 0 else -100000
            return e["value"]

        cp_before = cp(before_eval)
        cp_after = cp(after_eval)
        delta = cp_after - cp_before

        # Detect mistake based on eval drop
        if delta < -CENTI_PAWN_LOST:  # ~0.8 pawn loss
            mistakes.append({
                "game_id": game_json["id"],
                "ply": ply,
                "move": san_move,
                "fen_before": fen_before,
                "eval_drop": delta
            })

# Print mistakes
count = 0
random.shuffle(mistakes)
for m in mistakes:
    print(
        f"Game {m['game_id']} | Ply {m['ply']} | Move {m['move']} | Eval drop {m['eval_drop']}"
    )
    gui = ChessGUI(m['fen_before'], engine)
    gui.run()
    count += 1
    print(count, len(mistakes), count / len(mistakes))

# if __name__ == "__main__":
#     gui = ChessGUI()
#     gui.run()

