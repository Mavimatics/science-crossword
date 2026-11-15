# The Science Crossword

A daily math and science crossword at three levels, with every grid built by a search algorithm.
Play it at https://mavimatics.github.io/crossword/.

| Level | Grid | Words drawn from | Answers per puzzle |
|---|---|---|---|
| Easy | 5×5 | everyday science (ATOM, PRIME) | 5–6 |
| Intermediate | 13×13 | everyday + school/university (ENTROPY, LOGARITHM) | 15–21 |
| Guru | 15×15 | university + specialist (EIGENVECTOR, APOPTOSIS), harder clues | 15–21 |

There are 365 puzzles per level, one per day starting 1 January 2026, cycling after a year.

## How a grid is built

The puzzles are *criss-cross* style: themed words interlock with blank space between them, rather
than the dense newspaper style, which needs a huge list of short everyday filler words.

A grid is valid when every word crosses at least one other, crossing letters match, no letter sits
beside another unless they belong to crossing words, and no word runs into the end of another.

`generate.py` builds one by greedy placement:

1. Place a long word.
2. Try words from the pool in every position where they cross a letter already on the grid; reject
   positions that break a rule; place the one with the best score (crossings first, then length,
   with a little randomness).
3. Repeat until nothing fits or the word limit is reached.

Greedy placement can block itself, so each puzzle keeps the best of many complete attempts (150
for Easy, 40 for the larger grids), scored on words, crossings, filled squares and how much of the
grid is used.

Variety over a year comes from three rules: a word sits out the next few puzzles after it's used;
words used more than their fair share lose points when competing for a spot; and words with two
clues alternate between them.

## Files

- `words.txt`: the word list, one answer per line: `ANSWER | level | clue | harder clue`
- `generate.py`: builds the puzzles; pure Python 3, no dependencies
- `show.py`: prints a generated puzzle as text, for checking
- `out/`: the generated puzzles (`<level>-<chunk>.json`, 31 per file), `manifest.json`, `stats.json`

```bash
python3 generate.py                    # all levels, 365 each (about 6 minutes)
python3 generate.py --levels easy      # one level
python3 show.py out/guru-00.json 3     # print puzzle #4 of Guru
```

Each puzzle is stored as `{"n", "rows", "cols", "words": [[answer, clue, row, col, "a"|"d", number], ...]}`,
with words in the order they were placed.

## Notes

Answers ship with the puzzles, since the game runs entirely in the browser. Adding words to
`words.txt` and regenerating is the easiest way to reduce repeats. The generator checks that no
clue contains its own answer.
