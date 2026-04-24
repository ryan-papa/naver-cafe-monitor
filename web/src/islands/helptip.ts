/**
 * HelpTip island — `.helptip` 요소의 `?` 버튼 클릭으로 툴팁 토글.
 * ESC 또는 바깥 클릭 시 닫힘. initHelpTips()는 idempotent (중복 바인딩 방지).
 */

const BOUND = "helptipBound";

export function initHelpTips(): void {
  if (typeof document === "undefined") return;

  document.querySelectorAll<HTMLElement>("[data-helptip]").forEach((root) => {
    if (root.dataset[BOUND] === "1") return;
    root.dataset[BOUND] = "1";

    const trigger = root.querySelector<HTMLButtonElement>("[data-helptip-trigger]");
    const tip = root.querySelector<HTMLElement>("[data-helptip-tip]");
    if (!trigger || !tip) return;

    const setOpen = (open: boolean) => {
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) tip.removeAttribute("hidden");
      else tip.setAttribute("hidden", "");
    };

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = trigger.getAttribute("aria-expanded") === "true";
      setOpen(!isOpen);
    });

    document.addEventListener("mousedown", (e) => {
      if (!root.contains(e.target as Node)) setOpen(false);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") setOpen(false);
    });
  });
}
