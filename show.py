"""Print a generated puzzle as text: python3 show.py out/guru-00.json [index]"""
import json
import sys

puzzles = json.load(open(sys.argv[1]))
p = puzzles[int(sys.argv[2]) if len(sys.argv) > 2 else 0]
grid = [["." for _ in range(p["cols"])] for _ in range(p["rows"])]
for w, clue, r, c, d, num in p["words"]:
    for i, ch in enumerate(w):
        grid[r + (i if d == "d" else 0)][c + (i if d == "a" else 0)] = ch
print("\n".join(" ".join(row) for row in grid))
for d, name in (("a", "Across"), ("d", "Down")):
    print(name)
    for w, clue, r, c, dd, num in sorted(p["words"], key=lambda x: x[5]):
        if dd == d:
            print(f"  {num:2d}. {clue} ({len(w)})  [{w}]")
