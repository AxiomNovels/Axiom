// These sliders explore the guide; they do not submit profile votes.
document.querySelectorAll('.trait-guide-card').forEach((card) => {
  const control = card.querySelector('.trait-slider-control');
  const slider = control.querySelector('input');
  const output = control.querySelector('output');
  const descriptions = card.querySelectorAll('[data-score]');

  function showScore() {
    const score = Number(slider.value);
    output.value = `${score} / 100`;
    slider.style.setProperty('--score', `${score}%`);
    descriptions.forEach((description) => {
      description.hidden = Number(description.dataset.score) !== score;
    });
  }

  card.classList.add('has-trait-slider');
  card.querySelector('.trait-scale-list').setAttribute('aria-live', 'polite');
  slider.addEventListener('input', showScore);
  showScore();
  control.hidden = false;
});
