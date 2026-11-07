const root = document.documentElement;
const media = [
  '(prefers-reduced-motion: reduce)', '(max-width: 760px)',
  '(hover: none) and (pointer: coarse)',
].map((query) => matchMedia(query));
const [reduced, narrow, coarse] = media;
const network = navigator.connection;
let ceiling = 2, probing = false;

function update() {
  const lite = narrow.matches || coarse.matches || network?.saveData ||
    navigator.hardwareConcurrency <= 4 || navigator.deviceMemory <= 4;
  root.dataset.motion = reduced.matches ? 'off' : root.dataset.motionForce ||
    ['off', 'lite', 'full'][Math.min(lite ? 1 : 2, ceiling)];
  root.dataset.pageHidden = String(document.hidden);
}

for (const query of media) query.addEventListener('change', update);
network?.addEventListener?.('change', update);
document.addEventListener('visibilitychange', () => { update(); if (!document.hidden) probe(); });
update();

const scene = document.querySelector('.hero-cosmos');
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
      ceiling = Math.min(ceiling, average > 40 ? 0 : average > 24 ? 1 : 2);
      update();
      return;
    }
    previous = now;
    requestAnimationFrame(sample);
  }
  requestAnimationFrame(sample);
}

requestAnimationFrame(probe);
