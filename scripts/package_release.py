#!/usr/bin/env python3
"""Build and verify four standalone Zero Two sprite ZIPs (Python 3.9+)."""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path


VERSION = "1.2.0"
ROW_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]
CODEX_FILES = (
    "spritesheet.png", "spritesheet.webp", "manifest.json", "pet.json",
    "preview.gif", "look-preview.gif", "reference.png", "PROMPTS.md",
)
HD_REQUIRED = (
    "spritesheet.png", "spritesheet.webp", "manifest.json", "README.md",
    "preview.gif", "look-preview.gif", "comparison.png", "provenance.json",
    "validation.json",
)
REPO_URL = "https://github.com/FuXihhy/zero-two-desktop-pet"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def png_dimensions(path):
    with path.open("rb") as stream:
        header = stream.read(29)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Not a PNG: {path}")
    width, height = struct.unpack(">II", header[16:24])
    if header[25] != 6:
        raise ValueError(f"Expected RGBA PNG: {path}")
    return width, height


def required_file(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Required regular file missing: {path}")
    return path


def verify_layout(base, edition):
    manifest = json.loads(required_file(base / "manifest.json").read_text("utf-8"))
    cell = (192, 208) if edition == "codex" else (384, 416)
    expected = (cell[0] * 8, cell[1] * 11)
    atlas = manifest["atlas"]
    values = (atlas["columns"], atlas["rows"], atlas["cell_width"],
              atlas["cell_height"], atlas["width"], atlas["height"])
    if values != (8, 11, *cell, *expected):
        raise ValueError(f"Wrong {edition} atlas metadata in {base}")
    if png_dimensions(required_file(base / "spritesheet.png")) != expected:
        raise ValueError(f"PNG dimensions disagree with manifest in {base}")
    rows = manifest["rows"]
    if [row["row"] for row in rows] != list(range(11)):
        raise ValueError(f"Rows must be ordered 0–10 in {base}")
    if [row["frames"] for row in rows] != ROW_COUNTS:
        raise ValueError(f"Wrong required frame counts in {base}")
    if manifest.get("version") != VERSION:
        raise ValueError(f"Expected manifest version {VERSION} in {base}")
    if manifest.get("codex_compatible") is not (edition == "codex"):
        raise ValueError(f"Incorrect compatibility flag in {base}")
    if edition == "codex":
        pet = json.loads(required_file(base / "pet.json").read_text("utf-8"))
        if pet.get("spriteVersionNumber") != 2 or pet.get("spritesheetPath") != "spritesheet.webp":
            raise ValueError(f"Invalid Codex pet.json in {base}")
    else:
        frames = list((base / "frames").rglob("*.png"))
        if len(frames) != sum(ROW_COUNTS):
            raise ValueError(f"Expected 73 HD frames, got {len(frames)} in {base}")
        expected_frames = {
            base / "frames" / row["state"] / f"{index:02d}.png"
            for row in rows for index in range(row["frames"])
        }
        if set(frames) != expected_frames:
            raise ValueError(f"HD frame paths disagree with manifest in {base}")
        for frame in frames:
            if png_dimensions(required_file(frame)) != cell:
                raise ValueError(f"Wrong HD frame size: {frame}")
        validation = json.loads(required_file(base / "validation.json").read_text("utf-8"))
        if validation.get("valid") is not True:
            raise ValueError(f"HD structural validation did not pass in {base}")
    return manifest


def codex_readme(variant, manifest):
    name = "红制服 Q 版" if variant == "red-uniform" else "白礼服版"
    return f"""# 02 · {name} — Codex edition v{VERSION}

Codex 兼容素材，每帧 192 × 208 px，整张透明图集 1536 × 2288 px。
包含九组动作和十六方向视线，共 73 个有效帧；PNG / WebP 图集保持原先发布的字节。

打开 `preview.gif` 与 `look-preview.gif` 可查看动画。实际使用 `spritesheet.png`
或 `spritesheet.webp`；`pet.json` 是 Codex 桌宠元数据，`manifest.json` 定义动作与网格。
GIF 仅作预览，颜色和透明边缘以 PNG / WebP 为准。

若使用其他图集播放程序，行、列从零开始，裁切 `(192*c, 208*r, 192, 208)`。
按 manifest 中的有效帧数播放，不要播放透明占位格。动画速度由使用素材的程序决定。
此包是素材包，不包含独立桌面应用或安装器。

The Codex edition uses the original 192 × 208 cells in an 8 × 11 atlas.
Read `manifest.json` for state rows and frame counts. The separate HD 2× edition
uses 384 × 416 cells and is not accepted by the current Codex loader.

Files: PNG / WebP atlases, metadata, GIF previews, original reference image,
generation prompts, and `SHA256SUMS.txt`. Reference images retain their original
generation backgrounds. Every checksum is relative to this package directory.

[Project and all editions]({REPO_URL})

Unofficial fan art of Zero Two from *DARLING in the FRANXX*. The original artwork
was AI-generated. Character designs and animation poses are preserved.
""".encode("utf-8")


def source_payload(base, edition, variant, manifest):
    if edition == "codex":
        payload = {name: required_file(base / name).read_bytes() for name in CODEX_FILES}
        payload["README.md"] = codex_readme(variant, manifest)
    else:
        for name in HD_REQUIRED:
            required_file(base / name)
        payload = {}
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(base)
            if not path.is_file():
                continue
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Refusing symlink in HD package: {path}")
            if path.name == "SHA256SUMS.txt" or path.suffix == ".pyc":
                continue
            payload[relative.as_posix()] = path.read_bytes()
    checksums = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(payload.items()))
    payload["SHA256SUMS.txt"] = checksums.encode("utf-8")
    return payload


def write_archive(path, prefix, payload):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(f"{prefix}/{name}", date_time=(2026, 11, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"ZIP CRC check failed: {path}")
        actual = {name: archive.read(f"{prefix}/{name}") for name in payload}
        if actual != payload:
            raise ValueError(f"ZIP content readback failed: {path}")
        lines = actual["SHA256SUMS.txt"].decode("utf-8").splitlines()
        for line in lines:
            digest, name = line.split("  ", 1)
            if sha256(actual[name]) != digest:
                raise ValueError(f"ZIP SHA-256 check failed: {path}: {name}")


def update_repository_checksums(base, edition):
    if edition == "codex":
        files = [base / name for name in (*CODEX_FILES, "README.md")]
    else:
        files = [path for path in base.rglob("*") if path.is_file()
                 and path.name != "SHA256SUMS.txt"
                 and path.relative_to(base).parts[0] != "frames"
                 and not any(part.startswith(".") or part == "__pycache__"
                             for part in path.relative_to(base).parts)]
    lines = [f"{sha256(path.read_bytes())}  {path.relative_to(base).as_posix()}\n"
             for path in sorted(files)]
    (base / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.repo_root.resolve(), args.output_dir.resolve()
    packages = [
        ("red-uniform", "codex", root),
        ("white-dress", "codex", root / "white-dress"),
        ("red-uniform", "hd2x", root / "hd" / "red-uniform"),
        ("white-dress", "hd2x", root / "hd" / "white-dress"),
    ]
    # Validate every input before writing any archive.
    prepared = []
    for variant, edition, base in packages:
        manifest = verify_layout(base, edition)
        prepared.append((variant, edition, base, source_payload(base, edition, variant, manifest)))
    output.mkdir(parents=True, exist_ok=True)
    result = []
    for variant, edition, base, payload in prepared:
        name = f"02-{variant}-{edition}-v{VERSION}"
        path = output / f"{name}.zip"
        write_archive(path, name, payload)
        update_repository_checksums(base, edition)
        result.append({"name": path.name, "sha256": sha256(path.read_bytes()),
                       "size": path.stat().st_size, "files": len(payload), "verified": True})
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{item['sha256']}  {item['name']}\n" for item in result), encoding="utf-8")
    report = {"version": VERSION, "archives": result, "ok": True}
    (output / "package-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
