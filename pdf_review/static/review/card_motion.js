// Shared with right-hand comment selection. Scrolling itself is never animated.
export const CARD_MOTION_MS = 160;
export function animateCard(node, delta, opening = false, duration = CARD_MOTION_MS) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  node.getAnimations().forEach(animation => animation.cancel());
  return node.animate([
    { translate: `0 ${delta}px`, opacity: opening ? Math.max(0, 1 - duration / CARD_MOTION_MS) : 1 },
    { translate: '0 0', opacity: 1 },
  ], { duration, easing: 'ease-out' });
}
