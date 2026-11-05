const ROUNDING_PLACES = 6;

function roundCoordinate(value) {
  return Number(value.toFixed(ROUNDING_PLACES));
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function intersectClientRect(rect, bounds) {
  const left = Math.max(rect.left, bounds.left);
  const top = Math.max(rect.top, bounds.top);
  const right = Math.min(rect.right, bounds.right);
  const bottom = Math.min(rect.bottom, bounds.bottom);
  if (![left, top, right, bottom].every(Number.isFinite) || right <= left || bottom <= top) {
    return null;
  }
  return { left, top, right, bottom };
}

export function clientRectToPdfRectangle(clientRect, textLayerRect, viewport) {
  const clipped = intersectClientRect(clientRect, textLayerRect);
  if (!clipped || textLayerRect.width <= 0 || textLayerRect.height <= 0) {
    return null;
  }
  const scaleX = viewport.width / textLayerRect.width;
  const scaleY = viewport.height / textLayerRect.height;
  const viewportCorners = [
    [(clipped.left - textLayerRect.left) * scaleX, (clipped.top - textLayerRect.top) * scaleY],
    [(clipped.right - textLayerRect.left) * scaleX, (clipped.top - textLayerRect.top) * scaleY],
    [(clipped.left - textLayerRect.left) * scaleX, (clipped.bottom - textLayerRect.top) * scaleY],
    [(clipped.right - textLayerRect.left) * scaleX, (clipped.bottom - textLayerRect.top) * scaleY],
  ];
  const pdfCorners = viewportCorners.map(([x, y]) => viewport.convertToPdfPoint(x, y));
  if (pdfCorners.flat().some((value) => !Number.isFinite(value))) {
    return null;
  }
  const viewBox = viewport.viewBox;
  const minimumX = Math.min(viewBox[0], viewBox[2]);
  const maximumX = Math.max(viewBox[0], viewBox[2]);
  const minimumY = Math.min(viewBox[1], viewBox[3]);
  const maximumY = Math.max(viewBox[1], viewBox[3]);
  const x1 = clamp(Math.min(...pdfCorners.map(([x]) => x)), minimumX, maximumX);
  const y1 = clamp(Math.min(...pdfCorners.map(([, y]) => y)), minimumY, maximumY);
  const x2 = clamp(Math.max(...pdfCorners.map(([x]) => x)), minimumX, maximumX);
  const y2 = clamp(Math.max(...pdfCorners.map(([, y]) => y)), minimumY, maximumY);
  if (x2 - x1 <= 0 || y2 - y1 <= 0) {
    return null;
  }
  return [x1, y1, x2, y2].map(roundCoordinate);
}

export function deduplicateRectangles(rectangles) {
  const seen = new Set();
  return rectangles.filter((rectangle) => {
    const key = rectangle.join(",");
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

// A browser range can report adjacent text runs, spaces and enclosing spans.
// Normalize only the painted geometry; never modify the saved selector bundle.
export function visibleHighlightRectangles(rectangles, pageRotation = 0) {
  const unique = deduplicateRectangles(rectangles);
  const exposed = unique.filter((rectangle, index) => !unique.some((other, otherIndex) =>
    otherIndex !== index && other[0] <= rectangle[0] && other[1] <= rectangle[1] &&
    other[2] >= rectangle[2] && other[3] >= rectangle[3]));
  // Work in PDF units, independent of viewer zoom/rotation. Page rotation
  // metadata supplies the reading axis; never merge in the perpendicular axis,
  // where short successive lines could otherwise look like one vertical run.
  const pieces = exposed.map(rectangle => [...rectangle]);
  const order = new Map(pieces.map((rectangle, index) => [rectangle, index]));
  const along = pageRotation % 180 === 0 ? 0 : 1;
  const across = 1 - along;
  const lines = [];
  for (const rectangle of pieces.sort((a, b) =>
    (a[across] + a[across + 2]) - (b[across] + b[across + 2]) || a[along] - b[along])) {
    const thickness = rectangle[across + 2] - rectangle[across];
    const line = lines.find(candidate => {
      const tolerance = Math.min(thickness, candidate.thickness) * .15;
      return Math.abs(rectangle[across] - candidate.low) <= tolerance &&
        Math.abs(rectangle[across + 2] - candidate.high) <= tolerance;
    });
    if (line) line.rectangles.push(rectangle);
    else lines.push({ low: rectangle[across], high: rectangle[across + 2], thickness, rectangles: [rectangle] });
  }
  const result = [];
  for (const line of lines) {
    let previous = null;
    for (const rectangle of line.rectangles.sort((a, b) => a[along] - b[along])) {
      const thickness = Math.max(rectangle[across + 2], previous?.[across + 2] ?? -Infinity) -
        Math.min(rectangle[across], previous?.[across] ?? Infinity);
      const length = previous ? Math.max(previous[along + 2], rectangle[along + 2]) - previous[along] : 0;
      // Allow sub-point rounding gaps, not word-sized gaps or column gutters.
      // Avoid turning tiny boxes into a run across the text's reading axis.
      if (previous && length >= thickness &&
          rectangle[along] - previous[along + 2] <= Math.min(line.thickness * .05, .5)) {
        order.set(previous, Math.min(order.get(previous), order.get(rectangle)));
        for (const axis of [0, 1]) {
          previous[axis] = Math.min(previous[axis], rectangle[axis]);
          previous[axis + 2] = Math.max(previous[axis + 2], rectangle[axis + 2]);
        }
      } else {
        previous = rectangle;
        result.push(previous);
      }
    }
  }
  return result.sort((a, b) => order.get(a) - order.get(b));
}

export function pdfRectangleToCss(rectangle, viewport, textLayerRect) {
  if (!textLayerRect.width || !textLayerRect.height || !viewport.width || !viewport.height) {
    return null;
  }
  const [x1, y1, x2, y2] = rectangle;
  const pdfCorners = [[x1, y1], [x2, y1], [x1, y2], [x2, y2]];
  const viewportCorners = pdfCorners.map(([x, y]) => viewport.convertToViewportPoint(x, y));
  if (viewportCorners.flat().some((value) => !Number.isFinite(value))) {
    return null;
  }
  const viewportLeft = Math.min(...viewportCorners.map(([x]) => x));
  const viewportTop = Math.min(...viewportCorners.map(([, y]) => y));
  const viewportRight = Math.max(...viewportCorners.map(([x]) => x));
  const viewportBottom = Math.max(...viewportCorners.map(([, y]) => y));
  const cssScaleX = textLayerRect.width / viewport.width;
  const cssScaleY = textLayerRect.height / viewport.height;
  const result = {
    left: viewportLeft * cssScaleX,
    top: viewportTop * cssScaleY,
    width: (viewportRight - viewportLeft) * cssScaleX,
    height: (viewportBottom - viewportTop) * cssScaleY,
  };
  if (Object.values(result).some((value) => !Number.isFinite(value) || value < 0)) {
    return null;
  }
  return result;
}
