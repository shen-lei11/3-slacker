function triggerCoinDrop() {
  const area = document.getElementById('jar-drop-zone');
  if (!area) return;
  const coin = document.createElement('div');
  coin.className = 'coin animating-coin';
  coin.textContent = '$1';
  coin.style.left = '50%';
  coin.style.top = '-10px';
  coin.style.transform = 'translateX(-50%)';
  area.appendChild(coin);
  setTimeout(() => coin.remove(), 1600);
}

document.addEventListener('DOMContentLoaded', () => {
  const autoDrop = document.getElementById('auto-coin-drop');
  if (autoDrop) {
    triggerCoinDrop();
  }
});
