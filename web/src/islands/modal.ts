/**
 * Modal island — [data-modal-root] 요소들에 대해 열기/닫기 제어 + 포커스 트랩.
 *
 * Exports:
 *   - openModal(id): 모달 표시, 첫 포커서블로 포커스, focus-trap 활성화
 *   - closeModal(id): 모달 숨김, focus-trap 해제, 이전 포커스 복구
 *   - initModals(): close 버튼 / ESC / backdrop 클릭 바인딩 (idempotent)
 *
 * window 오염 없음. focus-trap npm 패키지 사용.
 */
import { createFocusTrap, type FocusTrap } from "focus-trap";

const BOUND = "modalBound";

interface TrapState {
  trap: FocusTrap;
  previousFocus: HTMLElement | null;
}

const traps = new Map<string, TrapState>();

function getRoot(id: string): HTMLElement | null {
  if (typeof document === "undefined") return null;
  return document.querySelector<HTMLElement>(`[data-modal-root="${id}"]`);
}

function focusFirst(root: HTMLElement): void {
  const focusable = root.querySelector<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (focusable) {
    focusable.focus();
  } else {
    root.setAttribute("tabindex", "-1");
    root.focus();
  }
}

export function openModal(id: string): void {
  const root = getRoot(id);
  if (!root) return;
  if (!root.hasAttribute("hidden")) return;

  const previousFocus =
    document.activeElement instanceof HTMLElement ? document.activeElement : null;

  root.removeAttribute("hidden");

  const trap = createFocusTrap(root, {
    escapeDeactivates: false,
    clickOutsideDeactivates: false,
    returnFocusOnDeactivate: false,
    fallbackFocus: root,
  });
  try {
    trap.activate();
  } catch {
    // focus-trap activation failure는 조용히 무시하고 수동 포커스
    focusFirst(root);
  }

  traps.set(id, { trap, previousFocus });
}

export function closeModal(id: string): void {
  const root = getRoot(id);
  if (!root) return;
  if (root.hasAttribute("hidden")) return;

  const state = traps.get(id);
  if (state) {
    try {
      state.trap.deactivate();
    } catch {
      // noop
    }
    traps.delete(id);
  }

  root.setAttribute("hidden", "");

  if (state?.previousFocus && document.body.contains(state.previousFocus)) {
    state.previousFocus.focus();
  }
}

export function initModals(): void {
  if (typeof document === "undefined") return;

  document.querySelectorAll<HTMLElement>("[data-modal-root]").forEach((root) => {
    if (root.dataset[BOUND] === "1") return;
    root.dataset[BOUND] = "1";

    const id = root.getAttribute("data-modal-root");
    if (!id) return;

    // Close buttons
    root.querySelectorAll<HTMLElement>("[data-modal-close]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        closeModal(id);
      });
    });

    // Backdrop click (backdrop 자체가 클릭되었을 때만; 내부 surface 클릭은 무시)
    root.addEventListener("mousedown", (e) => {
      if (e.target === root) {
        closeModal(id);
      }
    });

    // ESC
    root.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        closeModal(id);
      }
    });
  });
}
