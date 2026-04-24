/**
 * Resend cooldown island — 게시물 재발송 버튼 제어.
 *
 * - 30초 쿨다운을 localStorage `resend:${postId}:cooldownUntil` 에 저장
 * - 페이지 재로딩 후에도 남은 시간 자동 표시
 * - 클릭 시 csrfFetch POST, 성공 시 토스트 + 쿨다운 시작, 실패 시 토스트만
 */
import { csrfFetch } from "../lib/auth-client";

const COOLDOWN_MS = 30_000;

function key(postId: string): string {
  return `resend:${postId}:cooldownUntil`;
}

function showToast(msg: string, ok = true): void {
  const host =
    document.getElementById("toast-container") ||
    (() => {
      const d = document.createElement("div");
      d.id = "toast-container";
      d.className = "toast-container";
      document.body.appendChild(d);
      return d;
    })();
  const el = document.createElement("div");
  el.className = `toast-msg ${ok ? "toast-ok" : "toast-err"}`;
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

export function initResendCooldown(
  postId: string,
  button: HTMLButtonElement,
  apiBase = ""
): void {
  const label = button.dataset.label || button.textContent?.trim() || "재발송";
  let timerId: number | null = null;

  function tick(): void {
    const until = Number(localStorage.getItem(key(postId)) || 0);
    const remaining = until - Date.now();
    if (remaining <= 0) {
      if (timerId !== null) {
        window.clearInterval(timerId);
        timerId = null;
      }
      button.disabled = false;
      button.textContent = label;
      return;
    }
    const sec = Math.ceil(remaining / 1000);
    button.disabled = true;
    button.textContent = `${sec}초 대기`;
  }

  function startCooldown(): void {
    localStorage.setItem(key(postId), String(Date.now() + COOLDOWN_MS));
    if (timerId !== null) window.clearInterval(timerId);
    timerId = window.setInterval(tick, 500);
    tick();
  }

  async function onClick(): Promise<void> {
    const until = Number(localStorage.getItem(key(postId)) || 0);
    if (until > Date.now()) {
      tick();
      return;
    }
    button.disabled = true;
    const prev = button.textContent;
    button.textContent = "요청 중...";
    try {
      const res = await csrfFetch(`${apiBase}/api/posts/${postId}/resend`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || String(res.status));
      }
      showToast("카카오톡 발송 완료", true);
      startCooldown();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "알 수 없는 오류";
      showToast(`발송 실패: ${msg}`, false);
      button.disabled = false;
      button.textContent = prev || label;
    }
  }

  button.addEventListener("click", onClick);

  // 초기 상태: 쿨다운 남아있으면 즉시 반영
  const until = Number(localStorage.getItem(key(postId)) || 0);
  if (until > Date.now()) {
    timerId = window.setInterval(tick, 500);
    tick();
  }
}
