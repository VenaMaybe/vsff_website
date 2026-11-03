// Shared with right-hand comment selection. Scrolling itself is never animated.
export const CARD_MOTION_MS = 160;
export function animateCard(node, delta, opening = false, duration = CARD_MOTION_MS) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  node.getAnimations().forEach(animation => animation.cancel());
  node.animate([
    { transform: `translateY(${delta}px)`, opacity: opening ? Math.max(0, 1 - duration / CARD_MOTION_MS) : 1 },
    { transform: 'translateY(0)', opacity: 1 },
  ], { duration, easing: 'ease-out' });
}
