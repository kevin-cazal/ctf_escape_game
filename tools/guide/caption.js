
(() => {
  const show = () => {
    const t = sessionStorage.getItem('demo-cap'); if (!t || !document.body) return;
    let b = document.getElementById('demo-cap');
    if (!b) { b = document.createElement('div'); b.id = 'demo-cap'; document.body.appendChild(b); }
    b.textContent = t;
    b.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:99999;max-width:880px;' +
      'background:#0b0e1a;color:#fff;font:600 19px/1.35 system-ui,sans-serif;padding:12px 18px;' +
      'border-radius:10px;border-left:6px solid #00ff97;box-shadow:0 6px 20px rgb(0 0 0/.3)';
  };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', show) : show();
})();
