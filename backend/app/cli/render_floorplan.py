"""Decoder-only child: Linux seccomp or native Windows AppContainer; fail closed."""

import base64
import ctypes
import errno
import io
import json
import math
import os
import platform
import socket
import sys

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageOps

BYTE_LIMIT = 10 * 1024 * 1024
PIXEL_LIMIT = 32_000_000
SIDE_LIMIT = 10000
PAGE_LIMIT = 30
DISPLAY_LIMIT = 2048
Image.MAX_IMAGE_PIXELS = PIXEL_LIMIT
Image.init()


def isolate():
    if sys.platform == "win32":
        from app.core.windows_sandbox import assert_isolated

        assert_isolated()
        return
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise RuntimeError("Isolated decoding requires Linux x86_64/aarch64.")
    import resource

    for limit, value in (
        (resource.RLIMIT_AS, 1024**3),
        (resource.RLIMIT_CPU, 20),
        (resource.RLIMIT_FSIZE, 24 * 1024**2),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 16),
        (resource.RLIMIT_NPROC, 0),
    ):
        resource.setrlimit(limit, (value, value))
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)

    class Filter(ctypes.Structure):
        _fields_ = [
            ("code", ctypes.c_ushort),
            ("jt", ctypes.c_ubyte),
            ("jf", ctypes.c_ubyte),
            ("k", ctypes.c_uint32),
        ]

    class Program(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]

    if platform.machine() == "x86_64":
        arch = 0xC000003E
        denied = [
            2,
            85,
            257,
            437,
            41,
            42,
            43,
            44,
            45,
            46,
            47,
            49,
            50,
            53,
            288,
            59,
            322,
            56,
            57,
            58,
            435,
            101,
            62,
            200,
            234,
            165,
            166,
            161,
            82,
            83,
            84,
            86,
            87,
            88,
            90,
            91,
            92,
            93,
            94,
            258,
            259,
            260,
            263,
            264,
            265,
            266,
            268,
            272,
            308,
            316,
        ]
    else:
        arch = 0xC00000B7
        denied = [
            56,
            437,
            198,
            199,
            200,
            201,
            202,
            203,
            206,
            207,
            211,
            212,
            242,
            221,
            281,
            220,
            435,
            117,
            129,
            130,
            131,
            40,
            39,
            51,
            34,
            35,
            36,
            37,
            38,
            52,
            53,
            54,
            55,
            97,
            268,
            276,
        ]
    # Block asynchronous/handle-based I/O and cross-process memory/FD access too.
    denied.extend([425, 426, 427, 434, 438])
    denied.extend(
        [76, 77, 132, 235, 280, 188, 189, 190, 191, 192, 193, 298, 303, 304, 310, 311, 321, 323]
        if arch == 0xC000003E
        else [45, 46, 88, 5, 6, 7, 8, 9, 10, 241, 264, 265, 270, 271, 280, 282]
    )
    instructions = [
        Filter(0x20, 0, 0, 4),
        Filter(0x15, 1, 0, arch),
        Filter(0x06, 0, 0, 0x80000000),
        Filter(0x20, 0, 0, 0),
    ]
    if arch == 0xC000003E:
        instructions.extend([Filter(0x35, 0, 1, 0x40000000), Filter(0x06, 0, 0, 0x80000000)])
    for number in denied:
        instructions.extend(
            [Filter(0x15, 0, 1, number), Filter(0x06, 0, 0, 0x00050000 | errno.EPERM)]
        )
    instructions.append(Filter(0x06, 0, 0, 0x7FFF0000))
    array = (Filter * len(instructions))(*instructions)
    program = Program(len(instructions), array)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise RuntimeError("Kernel refused decoder isolation.")


def dimensions(width, height):
    if not (0 < width <= SIDE_LIMIT and 0 < height <= SIDE_LIMIT and width * height <= PIXEL_LIMIT):
        raise ValueError("Plan exceeds reference dimensions/pixel budget.")


def render(payload):
    raw = base64.b64decode(payload["bytes"], validate=True)
    if not raw or len(raw) > BYTE_LIMIT:
        raise ValueError("Invalid source byte count.")
    opts = payload["options"]
    page = opts["page"]
    if raw.startswith(b"%PDF-"):
        with pdfium.PdfDocument(raw) as document:
            if pdfium.raw.FPDF_GetSecurityHandlerRevision(document) >= 0:
                raise ValueError("Encrypted PDF is unsupported.")
            pages = len(document)
            if not 1 <= pages <= PAGE_LIMIT or not 1 <= page <= pages:
                raise ValueError("PDF page/count limit.")
            sizes = []
            for index in range(pages):
                width, height = document.get_page_size(index)
                width_px, height_px = math.ceil(width * 150 / 72), math.ceil(height * 150 / 72)
                dimensions(width_px, height_px)
                sizes.append({"page": index + 1, "width_px": width_px, "height_px": height_px})
            selected = sizes[page - 1]
            width, height = selected["width_px"], selected["height_px"]
            pdf_page = document[page - 1]
            rotation = pdf_page.get_rotation()
            bitmap = pdf_page.render(scale=150 / 72, rev_byteorder=True)
            try:
                image = bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
                pdf_page.close()
            media_type = "application/pdf"
            orientation = f"PDF page rotation {rotation}°, reference raster 150 DPI"
    elif raw.startswith(b"\x89PNG\r\n\x1a\n") or raw.startswith(b"\xff\xd8\xff"):
        if page != 1:
            raise ValueError("Images have one page.")
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in {"PNG", "JPEG"} or getattr(source, "n_frames", 1) != 1:
                raise ValueError("Only static PNG/JPEG.")
            dimensions(*source.size)
            source.load()
            normalized = ImageOps.exif_transpose(source)
            width, height = normalized.size
            orientation = "EXIF orientation normalized to top-left pixels"
            media_type = "image/png" if source.format == "PNG" else "image/jpeg"
            image = Image.new("RGB", normalized.size, "white")
            if normalized.mode in ("RGBA", "LA") or "transparency" in normalized.info:
                rgba = normalized.convert("RGBA")
                image.paste(rgba, mask=rgba.getchannel("A"))
            else:
                image.paste(normalized.convert("RGB"))
        pages = 1
        sizes = [{"page": 1, "width_px": width, "height_px": height}]
    else:
        raise ValueError("Unsupported signature.")
    dimensions(width, height)
    allowed = {
        "application/pdf": (".pdf",),
        "image/png": (".png",),
        "image/jpeg": (".jpg", ".jpeg"),
    }
    if not opts["filename"].lower().endswith(allowed[media_type]):
        raise ValueError("Signature/extension mismatch.")
    draw = ImageDraw.Draw(image)
    for rectangle in opts["redactions"]:
        x, y, w, h = (rectangle[k] for k in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
            raise ValueError("Mask outside page.")
        sx, sy = image.width / width, image.height / height
        draw.rectangle(
            (
                max(0, math.floor(x * sx) - 1),
                max(0, math.floor(y * sy) - 1),
                min(image.width, math.ceil((x + w) * sx) + 1),
                min(image.height, math.ceil((y + h) * sy) + 1),
            ),
            fill="white",
        )
    # Mask full reference pixels before resampling, preventing sensitive-edge bleed.
    image.thumbnail((DISPLAY_LIMIT, DISPLAY_LIMIT), Image.Resampling.LANCZOS)
    clean = Image.frombytes("RGB", image.size, image.tobytes())
    output = io.BytesIO()
    clean.save(output, format="PNG")
    return {
        "png": base64.b64encode(output.getvalue()).decode(),
        "metadata": {
            "page_count": pages,
            "pages": sizes,
            "page": page,
            "width_px": width,
            "height_px": height,
            "display_width_px": clean.width,
            "display_height_px": clean.height,
            "media_type": media_type,
            "orientation": orientation,
            "renderer": "pillow-pdfium-pixel-projection-v1",
            "redactions": opts["redactions"],
        },
    }


def main():
    try:
        probe = "--probe" in sys.argv
        payload = None if probe else json.loads(sys.stdin.buffer.read(15 * 1024 * 1024))
        isolate()
        if probe:
            denied = []
            forbidden = (
                sys.argv[sys.argv.index("--probe-file") + 1]
                if sys.platform == "win32"
                else "/etc/passwd"
            )

            def network():
                if sys.platform == "win32":
                    # Socket creation alone need not be forbidden on Windows.
                    with socket.socket() as sock:
                        sock.settimeout(1)
                        sock.connect(
                            ("127.0.0.1", int(sys.argv[sys.argv.index("--probe-port") + 1]))
                        )
                else:
                    socket.socket()

            for attempt in (lambda: open(forbidden), network):
                try:
                    attempt()
                except PermissionError:
                    denied.append(True)
                else:
                    denied.append(False)
            result = {
                "filesystem_denied": denied[0],
                "network_denied": denied[1],
                "database_env_absent": "DATABASE_URL" not in os.environ,
            }
            if sys.platform == "win32":
                folder = sys.argv[sys.argv.index("--probe-write-dir") + 1]
                try:
                    with open(os.path.join(folder, "must-not-write.txt"), "xb"):
                        pass
                except PermissionError:
                    result["filesystem_write_denied"] = True
                else:
                    result["filesystem_write_denied"] = False
        else:
            result = render(payload)
        print(json.dumps(result, separators=(",", ":"), allow_nan=False))
    except Exception:
        print(
            json.dumps(
                {
                    "error": "Cannot decode safely: check supported unencrypted PDF/PNG/JPEG, selected page, dimensions, redaction bounds and documented limits."
                }
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
