"""Dominant colour extraction from images using k-means clustering."""

from __future__ import annotations

import numpy as np
from PIL import Image
from sklearn.cluster import MiniBatchKMeans

from terratheme.palette.color_utils import rgb_euclidean, rgb_to_hsl


def load_image(path: str, max_dim: int = 150) -> np.ndarray:
    """Load an image, resize so longest side is *max_dim*, return (N, 3) RGB array."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = max_dim / max(w, h)
    if scale < 1:
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
    return np.array(img).reshape(-1, 3).astype(np.float64)


def _score_cluster(
    centroid: np.ndarray,
    population: int,
    total_pixels: int,
) -> float:
    """Score a cluster by population × adjusted saturation.

    Near-black/near-white/near-grey colours are penalised so that
    vibrant, character-defining hues rise to the top.
    """
    r, g, b = float(centroid[0]), float(centroid[1]), float(centroid[2])
    _h, s, l = rgb_to_hsl(r, g, b)

    score = (population / total_pixels) * (s + 0.3)

    if l < 0.05 or l > 0.95:
        score *= 0.05
    elif l < 0.1 or l > 0.9:
        score *= 0.2
    elif l < 0.15 or l > 0.85:
        score *= 0.5

    if s < 0.08:
        score *= 0.1

    return score


def extract_colors(path: str, n_colors: int = 5) -> list[tuple[int, int, int]]:
    """Extract *n_colors* dominant colours from an image.

    Returns a list of ``(R, G, B)`` tuples sorted by HSL lightness
    (dark → light).
    """
    pixels = load_image(path)
    total = pixels.shape[0]

    kmeans = MiniBatchKMeans(n_clusters=8, random_state=0, batch_size=4096)
    labels = kmeans.fit_predict(pixels)
    centroids = kmeans.cluster_centers_

    scored: list[tuple[float, float, float, float]] = []
    for i, center in enumerate(centroids):
        pop = int((labels == i).sum())
        if pop == 0:
            continue
        sc = _score_cluster(center, pop, total)
        r, g, b = float(center[0]), float(center[1]), float(center[2])
        scored.append((r, g, b, sc))

    scored.sort(key=lambda t: -t[3])

    selected: list[tuple[float, float, float, float]] = []
    candidates: list[tuple[float, float, float, float]] = []
    MIN_DIST = 30.0

    for r, g, b, sc in scored:
        if len(selected) >= n_colors:
            break
        if any(rgb_euclidean((r, g, b), s) < MIN_DIST for s in selected):
            candidates.append((r, g, b, sc))
            continue
        selected.append((r, g, b, sc))

    for r, g, b, sc in candidates:
        if len(selected) >= n_colors:
            break
        selected.append((r, g, b, sc))

    # Sort by HSL lightness (dark → light)
    selected.sort(key=lambda t: rgb_to_hsl(t[0], t[1], t[2])[2])

    result: list[tuple[int, int, int]] = []
    for r, g, b, _sc in selected[:n_colors]:
        result.append((
            max(0, min(255, round(r))),
            max(0, min(255, round(g))),
            max(0, min(255, round(b))),
        ))

    return result
