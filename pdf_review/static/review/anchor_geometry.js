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
