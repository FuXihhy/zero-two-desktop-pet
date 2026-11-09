# HD2x source re-export

`export_hd.py` recovers the approved poses from the original generated animation
strips. It does not enlarge either final 192×208 sprite atlas and does not draw,
generate or invent new artwork.

Run with Python 3.11+ and Pillow:

```sh
python export_hd.py --source-root /path/to/02-pets-migration --output-root /path/to/hd-output --variant both
```

The source package must retain its `B/decoded`, `D/decoded`, `pet_request.json`,
original final atlases and `tools/work-pets/scripts` directories. Use
`--pipeline-dir` to supply the same deterministic helper directory separately.
The script reads those files and writes only beneath the output directory.
The original final atlases are read only to generate the labelled comparison;
they do not supply pixels to the HD export.

Each edition has 384×416 cells in an 8×11 atlas, for a total of 3072×4576 pixels.
The output includes lossless PNG and WebP atlases, all 73 individual frame PNGs,
native-cell-size GIF previews, an image comparison, source hashes and per-row
transforms. It is a general-purpose sprite package and is not the fixed-size
ChatGPT Pets/Codex delivery atlas. Animation timing is supplied by the consumer;
the preview GIFs are examples.

The exporter retains the existing connected-component pose extraction and
chroma removal. Standard animation rows use a single shared viewport/scale,
including original vertical movement in jumping. All sixteen look poses share
one scale and the idle lower-body center/baseline. This shared scale includes
the longest pose in either look row, preventing the last look poses from getting
too close to a cell edge. A single edge-local cleanup pass follows, with the
helper's cell dimensions and edge radius adapted to HD2x and alpha unchanged.

No source image is enlarged. Native source resolution varies by action. The red
right-run strip needs a theoretical 1.008× scale to exactly fill twice the old
viewport; it is kept at 1.0 instead, so it is under 1% smaller than a literal
enlargement of the old normalized viewport. The red look family is normalized
against all sixteen source poses for consistent safe padding. These minor
registration differences are explicit in `provenance.json`.

`validation.json` checks the HD structure, 73 occupied/15 empty cells, safe
bounds, jump lift/landing, source scale, and exact decoded pixel equality of PNG
and lossless WebP. These are custom HD checks; they do not claim the official
fixed-size Pets upload validator supports HD. Visual review is still required.
Native source perimeter speckle or imperfect linework can remain. Re-exporting
recovers genuine detail but does not repair or redraw the original art.
