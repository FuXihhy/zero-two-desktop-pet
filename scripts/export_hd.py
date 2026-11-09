#!/usr/bin/env python3
"""Re-export approved Zero Two source strips at HD2x without enlarging an atlas.

Requires Pillow and the original migration package's deterministic processing
helpers. Source files are read-only. This is a general sprite-sheet export, not
the fixed-size ChatGPT Pets upload format.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

CELL = (384, 416)
COLUMNS, ROWS = 8, 11
STATE_COUNTS = [
    ("idle", 6), ("running-right", 8), ("running-left", 8), ("waving", 4),
    ("jumping", 5), ("failed", 8), ("waiting", 6), ("running", 6), ("review", 6),
    ("look-row-9", 8), ("look-row-10", 8),
]
NAMES = {"B": "02 · 红制服Q版", "D": "02 · 白礼服版"}
LABELS = ["000", "022.5", "045", "067.5", "090", "112.5", "135", "157.5",
          "180", "202.5", "225", "247.5", "270", "292.5", "315", "337.5"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def alpha_bbox(image: Image.Image, threshold: int = 16):
    return image.getchannel("A").point(lambda a: 255 if a > threshold else 0).getbbox()


def clean_rgb(image: Image.Image) -> Image.Image:
    raw = bytearray(image.tobytes())
    for i in range(0, len(raw), 4):
        if raw[i + 3] == 0:
            raw[i:i + 3] = b"\x00\x00\x00"
    return Image.frombytes("RGBA", image.size, bytes(raw))


def extract_groups(source: Path, count: int, key: tuple[int, int, int], extractor):
    with Image.open(source) as image:
        rgba = extractor.remove_chroma_background(image, key, 96.0)
    groups = extractor.component_frame_groups(rgba, count)
    if groups is None or len(groups) != count:
        raise ValueError(f"Could not recover {count} original pose groups: {source}")
    bounds = [extractor.component_bounds(group) for group in groups]
    return rgba, groups, bounds


def standard_frames(rgba, groups, bounds, extractor):
    """One source-coordinate viewport and scale for the whole animation row."""
    pad = 4  # Source-pixel padding, exactly as in the existing extractor.
    top = max(0, min(b[1] for b in bounds) - pad)
    bottom = min(rgba.height, max(b[3] for b in bounds) + pad)
    viewport = (max(b[2] - b[0] for b in bounds) + 2 * pad, bottom - top)
    scale = min((CELL[0] - 20) / viewport[0], (CELL[1] - 20) / viewport[1], 1.0)
    scaled = tuple(max(1, round(n * scale)) for n in viewport)
    output = []
    for group, bbox in zip(groups, bounds):
        crop = extractor.component_group_image(rgba, group, padding=pad)
        canvas = Image.new("RGBA", viewport)
        canvas.alpha_composite(crop, ((viewport[0] - crop.width) // 2, max(0, bbox[1] - pad) - top))
        if canvas.size != scaled:
            canvas = canvas.resize(scaled, Image.Resampling.LANCZOS)
        frame = Image.new("RGBA", CELL)
        frame.alpha_composite(canvas, ((CELL[0] - scaled[0]) // 2, (CELL[1] - scaled[1]) // 2))
        output.append(frame)
    return output, {"source_viewport": list(viewport), "source_shared_top": top,
                    "source_shared_bottom": bottom, "scale": scale,
                    "destination_viewport": list(scaled), "source_upscaled": scale > 1,
                    "registration": "shared row viewport; original vertical displacement preserved"}


def look_scale(cells, target, assembler):
    geometries = [assembler.cell_geometry(cell) for cell in cells]
    if any(g is None for g in geometries):
        raise ValueError("Empty original look pose")
    height = max(g.height for g in geometries)
    width = max(cell.getbbox()[2] - cell.getbbox()[0] for cell in cells)
    limits = [target.height / height, (CELL[0] - 20) / width, (CELL[1] - 20) / height, 1.0]
    margin = 10
    for cell, geometry in zip(cells, geometries):
        left, _, right, _ = cell.getbbox()
        center = geometry.lower_center_x - left
        if center > 0:
            limits.append((target.lower_center_x - margin) / center)
        if right - left - center > 0:
            limits.append((CELL[0] - margin - target.lower_center_x) / (right - left - center))
        limits.append((target.bottom - margin) / geometry.height)
    return min(limits)


def registered_look(cells, target, scale, assembler):
    output = []
    for cell in cells:
        bbox = cell.getbbox()
        geometry = assembler.cell_geometry(cell)
        crop = cell.crop(bbox)
        size = tuple(max(1, round(n * scale)) for n in crop.size)
        if crop.size != size:
            crop = crop.resize(size, Image.Resampling.LANCZOS)
        left = round(target.lower_center_x - (geometry.lower_center_x - bbox[0]) * scale)
        top = target.bottom - size[1]
        if left < 0 or top < 0 or left + size[0] > CELL[0] or top + size[1] > CELL[1]:
            raise ValueError("Registered look pose would clip")
        frame = Image.new("RGBA", CELL)
        frame.alpha_composite(crop, (left, top))
        # Apply the existing detached-component rule at twice the linear scale.
        output.append(assembler.remove_small_detached_components(frame))
    return output


def background_frame(frame, dark=False):
    canvas = Image.new("RGBA", CELL, "#252830" if dark else "#f3eef5")
    canvas.alpha_composite(frame)
    return canvas.convert("RGB")


def save_preview(frames, path: Path, duration=120):
    visible = [background_frame(frame) for frame in frames]
    visible[0].save(path, save_all=True, append_images=visible[1:], duration=duration,
                    loop=0, disposal=2, optimize=False)


def preview_comparison(frames, old_atlas, destination):
    rows = [(0, 0, "Idle"), (1, 2, "Running right"), (4, 2, "Jumping"), (9, 4, "Look right")]
    canvas = Image.new("RGB", (CELL[0] * 2, (CELL[1] + 28) * len(rows)), "#f3eef5")
    draw = ImageDraw.Draw(canvas)
    for i, (row, col, title) in enumerate(rows):
        y = i * (CELL[1] + 28)
        low = old_atlas.crop((col * 192, row * 208, (col + 1) * 192, (row + 1) * 208))
        low = low.resize(CELL, Image.Resampling.LANCZOS)
        draw.text((12, y + 8), title + " - original frame enlarged 2x", fill="#352a43")
        draw.text((CELL[0] + 12, y + 8), title + " - HD2x source re-export", fill="#352a43")
        canvas.paste(background_frame(low), (0, y + 28))
        canvas.paste(background_frame(frames[row][col]), (CELL[0], y + 28))
    canvas.save(destination)


def validate(atlas, all_frames, png_path, webp_path, provenance):
    errors = []
    if atlas.size != (3072, 4576):
        errors.append("Unexpected atlas dimensions")
    frame_records = []
    for row, (state, count) in enumerate(STATE_COUNTS):
        for col in range(8):
            cell = atlas.crop((col * CELL[0], row * CELL[1], (col + 1) * CELL[0], (row + 1) * CELL[1]))
            bbox = alpha_bbox(cell)
            if (bbox is not None) != (col < count):
                errors.append(f"Wrong occupancy at {row},{col}")
            if bbox:
                if bbox[0] < 4 or bbox[1] < 4 or bbox[2] > CELL[0] - 4 or bbox[3] > CELL[1] - 4:
                    errors.append(f"Near-edge artwork at {row},{col}: {bbox}")
                frame_records.append({"row": row, "column": col, "state": state, "visible_bbox": bbox})
    with Image.open(png_path) as png, Image.open(webp_path) as webp:
        exact = png.convert("RGBA").tobytes() == webp.convert("RGBA").tobytes()
    if not exact:
        errors.append("PNG and lossless WebP decoded RGBA differ")
    jump_bottoms = [alpha_bbox(frame)[3] for frame in all_frames[4]]
    source_jump_bottoms = [box[3] for box in provenance[4]["source_pose_bounds"]]
    if not min(jump_bottoms[1:-1]) < min(jump_bottoms[0], jump_bottoms[-1]) - 10:
        errors.append("Jump does not visibly rise above landing")
    if abs(jump_bottoms[0] - jump_bottoms[-1]) > 2:
        errors.append("Jump first and last ground contact differ")
    if any(row["transform"]["source_upscaled"] for row in provenance):
        errors.append("An original source pose was upscaled")
    return {"valid": not errors, "format": "general-purpose-hd2x", "codex_compatible": False,
            "dimensions": [3072, 4576], "cell_size": list(CELL), "required_frames": 73,
            "transparent_unused_cells": 15, "png_webp_rgba_identical": exact,
            "source_pixels_upscaled": False, "original_final_atlas_used_as_export_input": False,
            "jump": {"source_bottoms": source_jump_bottoms, "hd_bottoms": jump_bottoms,
                     "lift_pixels": max(jump_bottoms) - min(jump_bottoms),
                     "first_last_bottom_difference": jump_bottoms[-1] - jump_bottoms[0]},
            "frames": frame_records, "errors": errors,
            "scope": "Structural, encoding, source-scale and jump-registration checks; inspect previews for visual quality."}


def export_variant(source_root: Path, output_root: Path, variant: str, pipeline: Path):
    sys.path.insert(0, str(pipeline))
    extractor = importlib.import_module("extract_strip_frames")
    assembler = importlib.import_module("assemble_extended_atlas")
    despill = importlib.import_module("despill_chroma_edges")
    assembler.CELL_WIDTH, assembler.CELL_HEIGHT = CELL
    assembler.MIN_DETACHED_COMPONENT_PIXELS = 128 * 4
    despill.CELL_WIDTH, despill.CELL_HEIGHT = CELL
    source = source_root / variant
    destination = output_root / variant
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("frames", "previews", "qa"):
        (destination / name).mkdir(exist_ok=True)
    key = extractor.load_chroma_key(source / "decoded", None)
    all_frames, provenance, despill_reports = [], [], []
    target, shared_look_scale = None, None
    for row, (state, count) in enumerate(STATE_COUNTS):
        path = source / "decoded" / (state + ".png")
        rgba, groups, bounds = extract_groups(path, count, key, extractor)
        if row < 9:
            frames, transform = standard_frames(rgba, groups, bounds, extractor)
            if row == 0:
                target = assembler.cell_geometry(frames[0])
        else:
            cells = [extractor.component_group_image(rgba, group) for group in groups]
            if row == 9:
                # One common transform for all sixteen directions. Looking down
                # can be taller than the first eight poses; include it in the
                # shared safety bound instead of clipping or resizing one pose.
                next_source, next_groups, _ = extract_groups(source / "decoded" / "look-row-10.png", 8, key, extractor)
                next_cells = [extractor.component_group_image(next_source, group) for group in next_groups]
                shared_look_scale = look_scale(cells + next_cells, target, assembler)
            frames = registered_look(cells, target, shared_look_scale, assembler)
            transform = {"scale": shared_look_scale, "source_upscaled": shared_look_scale > 1,
                         "registration": "one common scale across all16 original poses; idle lower-body center and baseline",
                         "target_height": target.height, "target_lower_center_x": target.lower_center_x,
                         "target_bottom": target.bottom}
        output_frames = []
        (destination / "frames" / state).mkdir(exist_ok=True)
        for column, frame in enumerate(frames):
            before_alpha = frame.getchannel("A").tobytes()
            frame, report = despill.decontaminate_image(frame, chroma_key=key, edge_radius=10)
            frame = clean_rgb(frame)
            if before_alpha != frame.getchannel("A").tobytes():
                raise ValueError("Edge cleanup changed transparency")
            frame.save(destination / "frames" / state / f"{column:02}.png")
            output_frames.append(frame)
            despill_reports.append({"state": state, "column": column,
                                     "changed_pixels": report["changed_pixels"], "alpha_preserved": True})
        all_frames.append(output_frames)
        provenance.append({"row": row, "state": state, "frame_count": count,
                           "source": f"{variant}/decoded/{state}.png", "sha256": digest(path),
                           "source_dimensions": list(rgba.size), "source_pose_bounds": bounds,
                           "transform": transform})
        save_preview(output_frames, destination / "previews" / (state + ".gif"))
        print(f"{variant} {state}: {count} frames; source scale {transform['scale']:.6f}", flush=True)
    atlas = Image.new("RGBA", (CELL[0] * COLUMNS, CELL[1] * ROWS))
    for row, frames in enumerate(all_frames):
        for column, frame in enumerate(frames):
            atlas.alpha_composite(frame, (column * CELL[0], row * CELL[1]))
    png_path = destination / "spritesheet.png"
    webp_path = destination / "spritesheet.webp"
    atlas.save(png_path)
    atlas.save(webp_path, lossless=True, quality=100, method=6, exact=True)
    save_preview([f for row in all_frames[:9] for f in row], destination / "preview.gif")
    save_preview([f for row in all_frames[9:] for f in row], destination / "look-preview.gif", 160)
    with Image.open(source / "final" / "spritesheet-extended.png") as old:
        preview_comparison(all_frames, old.convert("RGBA"), destination / "comparison.png")
    manifest = {"name": NAMES[variant] + " · HD2x", "version": "1.2.0", "edition": "high-resolution",
                "codex_compatible": False, "format": "general-purpose-sprite-atlas", "spritesheet": "spritesheet.png",
                "webp": "spritesheet.webp", "atlas": {"columns": 8, "rows": 11, "cell_width": 384,
                    "cell_height": 416, "width": 3072, "height": 4576},
                "rows": [{"state": state, "row": row, "frames": count} for row, (state, count) in enumerate(STATE_COUNTS)],
                "look_directions": [{"degrees": float(label), "row": 9 + i // 8, "column": i % 8} for i, label in enumerate(LABELS)],
                "rendering": {"native_frame_size": [384, 416], "animation_timing": "Consumer controlled; GIF previews use 120ms/frame, look preview160ms/frame"},
                "notes": ["Recovered from original generated row strips, not enlarged from the 192x208 final atlas.",
                          "Original source pixels are never upscaled. The source resolution varies by state.",
                          "Not a ChatGPT Pets upload file or current Codex-compatible atlas."]}
    write_json(destination / "manifest.json", manifest)
    write_json(destination / "provenance.json", {"version": "1.2.0", "edition": "HD2x", "variant": variant,
                "original_atlas_upscaled": False, "source_upscaling_allowed": False,
                "chroma_key": "#%02X%02X%02X" % key, "chroma_threshold": 96.0,
                "edge_cleanup": {"algorithm": despill.ALGORITHM, "radius": 10, "alpha_preserved": True},
                "pipeline_helpers": {name: digest(pipeline / (name + ".py")) for name in
                    ("extract_strip_frames", "assemble_extended_atlas", "despill_chroma_edges")},
                "rows": provenance})
    write_json(destination / "qa" / "edge-cleanup.json", despill_reports)
    result = validate(atlas, all_frames, png_path, webp_path, provenance)
    write_json(destination / "validation.json", result)
    files = sorted(p for p in destination.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    (destination / "SHA256SUMS.txt").write_text("".join(f"{digest(p)}  {p.relative_to(destination).as_posix()}\n" for p in files), encoding="utf-8")
    if not result["valid"]:
        raise ValueError(f"{variant} validation failed: {result['errors']}")
    print(f"{variant} completed: {destination}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path, help="Original 02-pets-migration directory")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--pipeline-dir", type=Path, help="Defaults to source-root/tools/work-pets/scripts")
    parser.add_argument("--variant", choices=["B", "D", "both"], default="both")
    args = parser.parse_args()
    source = args.source_root.expanduser().resolve()
    output = args.output_root.expanduser().resolve()
    if output == source or source in output.parents:
        raise SystemExit("Output must be outside the original source package")
    pipeline = (args.pipeline_dir or source / "tools" / "work-pets" / "scripts").resolve()
    for variant in (["B", "D"] if args.variant == "both" else [args.variant]):
        export_variant(source, output, variant, pipeline)


if __name__ == "__main__":
    main()
