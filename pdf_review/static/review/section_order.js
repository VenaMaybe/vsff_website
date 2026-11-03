// Preserve unmapped logical slots; order mapped entries by canonical start.
export function orderSections(sections, placementFor = section => section.placement) {
  const logical = [...sections].sort((a, b) => a.position - b.position || a.section_id.localeCompare(b.section_id));
  const mapped = logical.filter(s => placementFor(s)?.start_page).sort((a, b) => {
    const x = placementFor(a), y = placementFor(b);
    const fraction = p => p.start_y == null ? 0 : (p.start_view_box[3] - p.start_y) / (p.start_view_box[3] - p.start_view_box[1]);
    return x.start_page - y.start_page || fraction(x) - fraction(y) || a.position - b.position;
  });
  let index = 0;
  return logical.map(s => placementFor(s)?.start_page ? mapped[index++] : s);
}
