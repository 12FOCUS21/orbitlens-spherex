const root = document.documentElement;
const media = [
  '(prefers-reduced-motion: reduce)', '(max-width: 760px)',
  '(hover: none) and (pointer: coarse)',
].map((query) => matchMedia(query));
const [reduced, narrow, coarse] = media;
const net = navigator.connection;
let cap = 2, probing = false;

function update() {
  const lite = narrow.matches || coarse.matches || net?.saveData ||
    navigator.hardwareConcurrency <= 4 || navigator.deviceMemory <= 4;
  root.dataset.motion = reduced.matches ? 'off' : root.dataset.motionForce ||
    ['off', 'lite', 'full'][Math.min(lite ? 1 : 2, cap)];
  root.dataset.pageHidden = String(document.hidden);
}

for (const query of media) query.addEventListener('change', update);
net?.addEventListener?.('change', update);
document.addEventListener('visibilitychange', () => { update(); if (!document.hidden) probe(); });
update();

const scene = document.querySelector('.hero-cosmos');
const hero = scene?.parentElement;
const fine = matchMedia('(hover: hover) and (pointer: fine)');
let raf = 0;
hero?.addEventListener('pointermove', ({ clientX, clientY }) => {
  if (root.dataset.motion !== 'full' || !fine.matches || hero.hasAttribute('data-motion-paused') || raf) return;
  raf = requestAnimationFrame(() => {
    const box = scene.getBoundingClientRect();
    const shift = (value) => `${Math.max(-3, Math.min(3, value)).toFixed(1)}px`;
    scene.style.setProperty('--px', shift(6 * (clientX - box.left) / box.width - 3));
    scene.style.setProperty('--py', shift(6 * (clientY - box.top) / box.height - 3));
    raf = 0;
  });
}, { passive: true });
hero?.addEventListener('pointerleave', () => {
  cancelAnimationFrame(raf);
  raf = 0;
  scene.style.removeProperty('--px');
  scene.style.removeProperty('--py');
});
if ('IntersectionObserver' in window) {
  const target = (node) => node === scene ? scene.parentElement : node;
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) target(entry.target).toggleAttribute('data-motion-paused', !entry.isIntersecting);
  });
  for (const node of [scene, document.querySelector('.viewer-empty'),
    document.querySelector('.connection'), document.querySelector('.progress')]) {
    if (!node) continue;
    const rect = node.getBoundingClientRect();
    target(node).toggleAttribute('data-motion-paused', rect.bottom <= 0 || rect.top >= innerHeight);
    observer.observe(node);
  }
}

function probe() {
  if (probing || document.hidden || root.dataset.motionForce) return;
  probing = true;
  let previous = 0, count = 0, total = 0;
  function sample(now) {
    if (document.hidden) { probing = false; return; }
    if (previous) { total += now - previous; count++; }
    if (count === 20) {
      const average = total / count;
      cap = Math.min(cap, average > 40 ? 0 : average > 24 ? 1 : 2);
      update();
      return;
    }
    previous = now;
    requestAnimationFrame(sample);
  }
  requestAnimationFrame(sample);
}

requestAnimationFrame(() => setTimeout(probe, 1200));
