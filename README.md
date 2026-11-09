# 02 · 红制服 Q 版桌宠

A red-uniform chibi **Zero Two** sprite pack, with nine animation states and sixteen look directions.

[Download the latest release](https://github.com/FuXihhy/zero-two-desktop-pet/releases/latest)

![Animation preview](preview.gif)

## 使用 / Usage

下载 Release 中的 `02-red-uniform-v1.0.0.zip`，解压后可直接打开 `preview.gif` 和 `look-preview.gif` 查看动画。透明 PNG 和 WebP 图集、网格信息及逐行动作定义都在包内，可供支持图集的桌宠或网页组件使用。

Download and extract the release ZIP. Open the GIF previews in a browser or image viewer; use `spritesheet.png` or `spritesheet.webp` with a sprite-sheet renderer. Read `manifest.json` for the grid and animation rows. This repository distributes the artwork and animation assets; it does not contain a standalone desktop application or installer.

## Files

- `spritesheet.png`: transparent 1536 × 2288 PNG atlas.
- `spritesheet.webp`: WebP version of the same atlas.
- `manifest.json`: 8 columns × 11 rows; each cell is 192 × 208 pixels.
- `preview.gif`: animation preview.
- `look-preview.gif`: sixteen-direction look preview.
- `reference.png`: original full-body design reference, with its blue generation background.
- `PROMPTS.md`: reference and animation-row generation prompts.
- `SHA256SUMS.txt`: SHA-256 checksums for the included files.

## Animation layout

Rows and columns are zero-indexed. For column `c` and row `r`, crop the rectangle `(192*c, 208*r, 192, 208)` from the atlas. Use only the active frame count for that row; unused cells are padding.

| Row | State | Active frames |
| --- | --- | --- |
| 0 | Idle | 6 |
| 1 | Running right | 8 |
| 2 | Running left | 8 |
| 3 | Waving | 4 |
| 4 | Jumping | 5 |
| 5 | Failed / blocked | 8 |
| 6 | Waiting | 6 |
| 7 | Working | 6 |
| 8 | Review / complete | 6 |
| 9–10 | Look directions | 16 total |

Look directions start at up (0°) and proceed clockwise in 22.5° steps, first across row 9, then across row 10. Animation speed is chosen by the consuming application.

![Look direction preview](look-preview.gif)

## About the artwork

This is an unofficial fan-art project featuring Zero Two from *DARLING in the FRANXX*. The supplied AI-generated artwork and final animation atlas are preserved without redrawing. The release contains the red-uniform chibi variant used on Haiyang Huang's personal homepage.
