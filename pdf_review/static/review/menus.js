// One disclosure/menu grammar for server pages and the independent viewer shell.
export function syncMenuValues() {
  document.querySelectorAll("[data-menu-input]").forEach((item) => {
    const control = document.getElementById(item.dataset.menuInput);
    item.setAttribute("aria-checked", String(control?.value === item.dataset.menuValue));
  });
}

function position(menu) {
  const popup = menu.querySelector(":scope > .toolbar-popover");
  if (!popup || !menu.open) return;
  const row = menu.querySelector(":scope > summary").getBoundingClientRect();
  const submenu = menu.classList.contains("submenu");
  popup.style.maxHeight = `${innerHeight - 16}px`;
  const width = popup.offsetWidth, height = popup.offsetHeight;
  let left = submenu ? row.right + 3 : row.right - width;
  if (submenu && left + width > innerWidth - 8) left = row.left - width - 3;
  left = Math.max(8, Math.min(innerWidth - width - 8, left));
  const top = Math.max(8, Math.min(innerHeight - height - 8, submenu ? row.top : row.bottom + 2));
  popup.style.left = `${left}px`;
  popup.style.top = `${top}px`;
  popup.dataset.side = submenu && left < row.left ? "left" : "right";
}

export function closeMenus(focus = false) {
  const menus = [...document.querySelectorAll(".toolbar-menu[open]")];
  menus.forEach((menu) => { menu.open = false; });
  if (focus && menus.length) menus[0].querySelector("summary").focus();
}

export function bindMenuDismissal(doc) {
  doc.addEventListener("pointerdown", (event) => {
    document.querySelectorAll(".toolbar-menu[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  doc.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const menu = event.target.closest?.(".toolbar-menu[open]");
    if (menu) { menu.open = false; menu.querySelector("summary").focus(); }
    else closeMenus(true);
  });
}

document.querySelectorAll(".toolbar-menu").forEach((menu) => {
  const summary = menu.querySelector(":scope > summary");
  summary.setAttribute("aria-haspopup", "menu");
  summary.setAttribute("aria-expanded", String(menu.open));
  menu.addEventListener("toggle", () => {
    summary.setAttribute("aria-expanded", String(menu.open));
    if (menu.open) {
      menu.parentElement.querySelectorAll(":scope > .toolbar-menu[open]").forEach((sibling) => { if (sibling !== menu) sibling.open = false; });
      position(menu);
    } else menu.querySelectorAll(".toolbar-menu[open]").forEach((child) => { child.open = false; });
  });
});
document.addEventListener("click", (event) => {
  const item = event.target.closest("[data-menu-input]");
  if (item) {
    const control = document.getElementById(item.dataset.menuInput);
    control.value = item.dataset.menuValue;
    control.dispatchEvent(new Event("change", { bubbles: true }));
  }
  const action = event.target.closest(".toolbar-popover button, .toolbar-popover a");
  // Keep required confirmation fields visible when browser validation blocks a POST.
  if (action?.form && !action.form.checkValidity()) return;
  if (action && !action.closest("[data-keep-menu-open]")) closeMenus(!action.hasAttribute('data-left-card'));
});
document.addEventListener("change", syncMenuValues);
document.addEventListener("keydown", (event) => {
  const trigger = event.target.closest("summary");
  const menu = event.target.closest(".toolbar-menu, .tools-panel");
  if (!menu) return;
  const icons=event.target.closest('.tools-icon-grid');
  if(icons&&['ArrowLeft','ArrowRight'].includes(event.key)){
    const buttons=[...icons.querySelectorAll('button')].filter(button=>!button.disabled);
    if(!buttons.length)return;
    event.preventDefault();
    const index=buttons.indexOf(document.activeElement),direction=event.key==='ArrowRight'?1:-1;
    buttons[(index+direction+buttons.length)%buttons.length].focus();return;
  }
  if (event.key === "ArrowLeft" && menu.classList.contains("submenu")) {
    event.preventDefault(); menu.open = false; menu.querySelector("summary").focus(); return;
  }
  if (trigger && ["ArrowRight", "ArrowDown", "ArrowUp"].includes(event.key)) {
    event.preventDefault(); menu.open = true; position(menu);
    const rows = menu.querySelector(":scope > .toolbar-popover").querySelectorAll(":scope > .tools-icon-grid > button, :scope > button, :scope > a, :scope > details > summary, :scope > form > button");
    rows[event.key === "ArrowUp" ? rows.length - 1 : 0]?.focus(); return;
  }
  if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    const popup = event.target.closest(".toolbar-popover");
    if (!popup) return;
    const rows = [...popup.querySelectorAll(":scope > .tools-icon-grid > button, :scope > button, :scope > a, :scope > details > summary, :scope > form > button")].filter((item) => !item.disabled);
    if (!rows.length) return;
    event.preventDefault();
    const index = rows.indexOf(document.activeElement);
    rows[event.key === "Home" ? 0 : event.key === "End" ? rows.length - 1 : (index + (event.key === "ArrowUp" ? -1 : 1) + rows.length) % rows.length].focus();
  }
});
bindMenuDismissal(document);
window.addEventListener("resize", () => document.querySelectorAll(".toolbar-menu[open]").forEach(position));
// Form validation can scroll a required field into view. Keep that confirmation
// open; reposition fixed menus as the owning page moves instead of hiding it.
document.addEventListener("scroll", () => document.querySelectorAll(".toolbar-menu[open]").forEach(position), true);
syncMenuValues();
