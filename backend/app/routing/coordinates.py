import math
from dataclasses import dataclass


@dataclass(frozen=True)
class IndoorPoint:
    frame_id: str
    x_px: float
    y_px: float


def indoor_to_leaflet(point: IndoorPoint, height_px: float) -> tuple[float, float]:
    if not all(math.isfinite(v) for v in (point.x_px, point.y_px, height_px)) or height_px <= 0:
        raise ValueError("Invalid image coordinates")
    if point.x_px < 0 or not 0 <= point.y_px <= height_px:
        raise ValueError("Point outside image")
    return height_px - point.y_px, point.x_px


def calibrated_length(points: list[IndoorPoint], metres_per_pixel: float | None) -> float:
    if metres_per_pixel is None or not math.isfinite(metres_per_pixel) or metres_per_pixel <= 0:
        raise ValueError("A verified positive scale is required")
    if len(points) < 2 or len({p.frame_id for p in points}) != 1:
        raise ValueError("A path must stay in one floor-local frame")
    if any(not math.isfinite(v) or v < 0 for p in points for v in (p.x_px, p.y_px)):
        raise ValueError("Invalid local coordinate")
    return (
        sum(
            math.hypot(b.x_px - a.x_px, b.y_px - a.y_px)
            for a, b in zip(points, points[1:], strict=False)
        )
        * metres_per_pixel
    )
