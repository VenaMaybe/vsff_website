function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function pageLabel(anchor) {
  const pages = anchor.segments.map((segment) => segment.page_number);
  return pages.length === 1 ? `Page ${pages[0]}` : `Pages ${pages[0]}–${pages.at(-1)}`;
}

function technicalDetails(anchor, viewportDetails) {
  return {
    anchor_id: anchor.anchor_id,
    version_id: anchor.document_version_id,
    selector_version: anchor.selector_version,
    anchor_schema_version: anchor.anchor_schema_version,
    created_at: anchor.created_at,
    segments: anchor.segments.map((segment) => ({
      segment_index: segment.segment_index,
      page_number: segment.page_number,
      exact_text: segment.exact_text,
      prefix: segment.prefix,
      suffix: segment.suffix,
      text_start: segment.text_start,
      text_end: segment.text_end,
      page_text_sha256: segment.page_text_sha256,
      pdf_view_box: segment.pdf_view_box,
      pdf_rectangles: segment.rectangles,
      capture_viewport: segment.capture_viewport,
      current_rendered_viewport: viewportDetails(segment.page_number),
      validation: segment.validation,
    })),
  };
}

export function renderAnchorInspector(container, anchors, actions) {
  container.replaceChildren();
  const count = element("p", "anchor-panel-count", `${anchors.length} saved anchor${anchors.length === 1 ? "" : "s"}`);
  container.append(count);
  if (!anchors.length) {
    container.append(element("p", "anchor-panel-empty", "Select PDF text, then use Save selection."));
    return;
  }
  for (const anchor of anchors) {
    const card = element("article", "anchor-debug-card");
    const heading = element("div", "anchor-debug-heading");
    heading.append(
      element("strong", "", `#${anchor.anchor_id.slice(0, 8)}`),
      element("span", "", `${pageLabel(anchor)} · ${anchor.segments.length} segment${anchor.segments.length === 1 ? "" : "s"}`)
    );
    const quote = element("blockquote", "anchor-debug-quote", anchor.selection_text);
    const validation = anchor.segments.every(
      (segment) => segment.validation.geometry === "validated" && segment.validation.selector === "verified"
    ) ? "Geometry and selectors validated" : "Geometry validated; selector offsets unavailable";
    const status = element("p", "anchor-debug-validation", validation);
    const controls = element("div", "anchor-debug-controls");
    const navigate = element("button", "anchor-small-button", "Go to");
    navigate.type = "button";
    navigate.addEventListener("click", () => actions.navigate(anchor));
    const remove = element("button", "anchor-small-button danger", "Delete");
    remove.type = "button";
    remove.addEventListener("click", () => actions.remove(anchor));
    controls.append(navigate);
    if (actions.canMutate) controls.append(remove);
    const details = element("details", "anchor-technical-details");
    details.append(element("summary", "", "Technical details"));
    details.addEventListener("toggle", () => {
      if (details.open) {
        details.querySelector("pre")?.remove();
        details.append(
          element("pre", "", JSON.stringify(technicalDetails(anchor, actions.viewportDetails), null, 2))
        );
      }
    });
    card.append(heading, quote, status, controls, details);
    container.append(card);
  }
}
