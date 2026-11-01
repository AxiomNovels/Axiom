async function loadGuideAuthorAvatar() {
  const avatar = document.querySelector('[data-guide-author-avatar]');
  if (!avatar) return;
  try {
    const response = await fetch(`${API_BASE}/api/team`);
    if (!response.ok) return;
    const payload = await response.json();
    const author = (payload.members || []).find((member) => member.username?.toLowerCase() === 'wafflehunter');
    if (!author?.avatar_url) return;
    const image = document.createElement('img');
    image.alt = '';
    image.referrerPolicy = 'no-referrer';
    image.addEventListener('load', () => avatar.replaceChildren(image), { once: true });
    image.src = author.avatar_url;
  } catch {
    // Keep the author's initial if their public profile picture is unavailable.
  }
}

loadGuideAuthorAvatar();

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
