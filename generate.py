"""Build a year of criss-cross puzzles at three levels from the word list in words.txt.

    python3 generate.py [--count 365] [--levels easy,intermediate,guru] [--out out]

How a grid is built (one attempt):
  1. Put a long word somewhere on the grid.
  2. Repeatedly look for any word from the pool that can cross a letter already on the grid,
     in any position where it fits the rules below; place the best-scoring one.
  3. Stop when nothing else fits or the grid is full enough.
Rules for a placement: inside the grid; crossing letters must match; no letter may sit side by
side with another unless the two belong to crossing words; a word can't run straight into
another one; every word (after the first) crosses at least one already placed.
Greedy placement can paint itself into a corner, so each puzzle keeps the best of many attempts.

Variety: a word "rests" for a few puzzles after it's used, words used more than their fair share
lose points when competing for a spot, and words with two clues alternate.
Output: out/<level>-<chunk>.json (31 puzzles per file), out/manifest.json, out/stats.json.
"""
import argparse
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHUNK = 31  # puzzles per data file, so the page loads one small file at a time

LEVELS = {
    # size: grid side; lengths: allowed answer lengths; mix: share of the pool from each word level;
    # words: (minimum, maximum) answers per puzzle; rest: puzzles a word sits out after use;
    # attempts: tries per puzzle (the best one is kept); sample: candidate words considered per step.
    "easy": dict(size=5, lengths=(3, 5), mix={1: 1.0}, words=(5, 7), rest=8, attempts=150, sample=200),
    "intermediate": dict(size=13, lengths=(4, 11), mix={1: 0.4, 2: 0.6}, words=(14, 22), rest=4,
                         attempts=40, sample=80),
    "guru": dict(size=15, lengths=(4, 15), mix={2: 0.35, 3: 0.65}, words=(15, 26), rest=3,
                 attempts=40, sample=80),
}


def load_words(path=HERE / "words.txt"):
    words = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(" | ")]
        answer, level, clues = parts[0], int(parts[1]), [c for c in parts[2:] if c]
        assert answer.isalpha() and answer.isupper(), f"bad answer {answer!r}"
        assert answer not in words, f"duplicate {answer}"
        assert 1 <= level <= 3 and 1 <= len(clues) <= 2, line
        for clue in clues:  # a clue must not give the answer away
            assert answer.lower() not in clue.lower(), f"{answer}: answer appears in clue {clue!r}"
        words[answer] = {"level": level, "clues": clues}
    return words


class Grid:
    def __init__(self, size):
        self.size = size
        self.cells = {}                       # (row, col) -> letter
        self.dirs = defaultdict(set)          # (row, col) -> {"a", "d"}: directions covering the cell
        self.placed = []                      # [answer, row, col, dir] in placement order
        self.by_letter = defaultdict(set)     # letter -> cells covered in one direction only

    @staticmethod
    def step(d):
        return (0, 1) if d == "a" else (1, 0)

    def fits(self, word, r, c, d):
        """Number of crossings if the word fits at (r, c) in direction d, else -1."""
        dr, dc = self.step(d)
        n, size = len(word), self.size
        if r < 0 or c < 0 or r + dr * (n - 1) >= size or c + dc * (n - 1) >= size:
            return -1
        if (r - dr, c - dc) in self.cells or (r + dr * n, c + dc * n) in self.cells:
            return -1  # would run into another word
        crossings = 0
        for i, ch in enumerate(word):
            cell = (r + dr * i, c + dc * i)
            have = self.cells.get(cell)
            if have is not None:
                if have != ch or d in self.dirs[cell]:
                    return -1
                crossings += 1
            elif (cell[0] + dc, cell[1] + dr) in self.cells or (cell[0] - dc, cell[1] - dr) in self.cells:
                return -1  # a side neighbor would form an unintended two-letter run
        return crossings if crossings < n else -1

    def place(self, word, r, c, d):
        dr, dc = self.step(d)
        for i, ch in enumerate(word):
            cell = (r + dr * i, c + dc * i)
            self.cells[cell] = ch
            self.dirs[cell].add(d)
            if len(self.dirs[cell]) == 1:
                self.by_letter[ch].add(cell)
            else:
                self.by_letter[ch].discard(cell)
        self.placed.append([word, r, c, d])

    def candidates(self, word):
        """Every placement of `word` that crosses an open letter on the grid."""
        for i, ch in enumerate(word):
            for (r, c) in self.by_letter.get(ch, ()):
                d = "d" if "a" in self.dirs[(r, c)] else "a"  # cross the existing word
                dr, dc = self.step(d)
                yield r - dr * i, c - dc * i, d

    def valid(self):
        """Every run of two or more letters, across and down, is a placed word."""
        words = {(r, c, d): w for w, r, c, d in self.placed}
        for d in "ad":
            dr, dc = self.step(d)
            for (r, c) in self.cells:
                if (r - dr, c - dc) in self.cells:
                    continue  # not the start of a run
                n = 1
                while (r + dr * n, c + dc * n) in self.cells:
                    n += 1
                if n > 1 and (r, c, d) not in words:
                    return False
        return True

    def crossings(self):
        return sum(len(v) == 2 for v in self.dirs.values())


def attempt(pool, wts, cfg, rng, penalty):
    size, (_, most) = cfg["size"], cfg["words"]
    g = Grid(size)
    longish = [w for w in pool if len(w) >= max(3, int(0.6 * size))] or pool
    first = rng.choice(longish)
    d = rng.choice("ad")
    along = rng.randint(0, size - len(first))
    across = rng.randint(size // 4, size - 1 - size // 4) if size > 5 else rng.randint(0, size - 1)
    g.place(first, *((across, along) if d == "a" else (along, across)), d)
    used = {first}
    while len(g.placed) < most:
        best, best_score = None, -1.0
        for w in set(rng.choices(pool, weights=wts, k=cfg["sample"])):  # weighted by the level mix
            if w in used:
                continue
            for r, c, d in g.candidates(w):
                x = g.fits(w, r, c, d)
                if x < 1:
                    continue
                score = 10 * x + 0.5 * len(w) + 4 * rng.random() - penalty[w]
                if score > best_score:
                    best, best_score = (w, r, c, d), score
        if best is None:
            break
        g.place(*best)
        used.add(best[0])
    return g


def layout_score(g):
    rows = {r for r, _ in g.cells}
    cols = {c for _, c in g.cells}
    span = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1) / g.size ** 2
    return 2 * g.crossings() + len(g.placed) + 10 * len(g.cells) / g.size ** 2 + 5 * span


def build(cfg, pool, wts, rng, penalty):
    """Best of cfg['attempts'] grids that meet the minimum word count and span the grid."""
    best, best_score = None, -1.0
    for _ in range(cfg["attempts"]):
        g = attempt(pool, wts, cfg, rng, penalty)
        rows = {r for r, _ in g.cells}
        cols = {c for _, c in g.cells}
        if (len(g.placed) < cfg["words"][0] or len(rows) < g.size - 1 or len(cols) < g.size - 1
                or not g.valid()):
            continue
        s = layout_score(g) - sum(penalty[w] for w, *_ in g.placed) / 10
        if s > best_score:
            best, best_score = g, s
    return best


def number(placed):
    """Standard crossword numbering: number each start cell in reading order."""
    starts = sorted({(r, c) for _, r, c, _ in placed})
    num = {cell: i + 1 for i, cell in enumerate(starts)}
    return [num[(r, c)] for _, r, c, _ in placed]


def pick_clue(word, info, level, uses):
    clues = info["clues"]
    if level == "easy" or len(clues) == 1:
        return clues[0]
    start = 1 if level == "guru" else 0  # Guru leads with the harder clue
    return clues[(start + uses) % len(clues)]


def generate_level(name, words, count, seed):
    cfg = LEVELS[name]
    lo, hi = cfg["lengths"]
    by_level = {k: [w for w, info in words.items() if info["level"] == k and lo <= len(w) <= hi]
                for k in cfg["mix"]}
    rng = random.Random(seed)
    last_used, uses, puzzles, failures = {}, Counter(), [], 0
    for n in range(1, count + 1):
        # Pool for this puzzle: rested words only, drawn from each level in proportion to the mix.
        fresh = {k: [w for w in ws if n - last_used.get(w, -99) > cfg["rest"]] for k, ws in by_level.items()}
        weights = {k: cfg["mix"][k] / max(1, len(ws)) for k, ws in fresh.items()}
        pool = [w for ws in fresh.values() for w in ws]
        wts = [weights[words[w]["level"]] for w in pool]  # each level gets its share of the draws
        # Words used more than their fair share so far lose points, so easy fillers don't dominate.
        fair = sum(uses.values()) / max(1, sum(len(ws) for ws in by_level.values()))
        penalty = {w: 6 * max(0.0, uses[w] - fair) for w in pool}
        g = None
        while g is None:
            g = build(cfg, pool, wts, rng, penalty)
            failures += g is None
        rows = [r for r, _ in g.cells]
        cols = [c for _, c in g.cells]
        r0, c0 = min(rows), min(cols)
        entries = []
        for (w, r, c, d), num in zip(g.placed, number(g.placed)):
            entries.append([w, pick_clue(w, words[w], name, uses[w]), r - r0, c - c0, d, num])
            last_used[w], uses[w] = n, uses[w] + 1
        puzzles.append({"n": n, "rows": max(rows) - r0 + 1, "cols": max(cols) - c0 + 1, "words": entries})
        if n % 25 == 0:
            print(f"  {name}: {n}/{count}", flush=True)
    return puzzles, uses, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=365)
    ap.add_argument("--levels", default="easy,intermediate,guru")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    words = load_words()
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    stats = json.loads((out / "stats.json").read_text()) if (out / "stats.json").exists() else {}
    stats["words_in_list"] = len(words)
    stats["words_by_level"] = Counter(str(info["level"]) for info in words.values())
    for i, name in enumerate(args.levels.split(",")):
        start = time.time()
        puzzles, uses, failures = generate_level(name, words, args.count, args.seed + i)
        for k in range(0, len(puzzles), CHUNK):
            (out / f"{name}-{k // CHUNK:02d}.json").write_text(
                json.dumps(puzzles[k:k + CHUNK], separators=(",", ":")))
        n_words = [len(p["words"]) for p in puzzles]
        stats[name] = {
            "puzzles": len(puzzles), "size": LEVELS[name]["size"],
            "words_per_puzzle": round(sum(n_words) / len(n_words), 1),
            "min_words": min(n_words), "max_words": max(n_words),
            "distinct_words": len(uses), "most_uses": uses.most_common(1)[0],
            "attempts_per_puzzle": LEVELS[name]["attempts"], "rebuilds": failures,
            "seconds": round(time.time() - start),
        }
        print(name, stats[name], flush=True)
    manifest = {"chunk": CHUNK, "epoch": "2026-01-01",
                "levels": {k: {"count": v["puzzles"], "size": v["size"]}
                           for k, v in stats.items() if isinstance(v, dict) and "puzzles" in v}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (out / "stats.json").write_text(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
