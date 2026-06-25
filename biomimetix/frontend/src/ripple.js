/* Cursor-positioned ripple: spawns a DOM span at the exact click coordinates */
export function createRipple(e, color = 'rgba(63, 207, 196, 0.40)') {
  const el = e.currentTarget;
  const rect = el.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  const x = e.clientX - rect.left - size / 2;
  const y = e.clientY - rect.top - size / 2;
  const span = document.createElement('span');
  Object.assign(span.style, {
    position: 'absolute', borderRadius: '50%',
    width: `${size}px`, height: `${size}px`,
    left: `${x}px`, top: `${y}px`,
    background: color,
    pointerEvents: 'none',
    animation: 'cursorRipple 600ms ease-out forwards',
    zIndex: 0,
  });
  el.appendChild(span);
  setTimeout(() => span.remove(), 620);
}
