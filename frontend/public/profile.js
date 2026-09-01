function requireSession() {
  if (!getAccessToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

const preferredTags = new Set();
let allTags = [];

function renderPreferredTags() {
  const container = document.querySelector("[data-selected-tags]");
  container.innerHTML = "";
  if (!preferredTags.size) {
    container.innerHTML = "<p>No tag preferences added yet.</p>";
    return;
  }
  preferredTags.forEach((tag) => {
    const chip = document.createElement("div");
    chip.className = "selected-tag";
    const name = document.createElement("span");
    name.textContent = tag;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "tag-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${tag}`);
    remove.addEventListener("click", () => {
      preferredTags.delete(tag);
      renderPreferredTags();
      renderSuggestions();
    });
    chip.append(name, remove);
    container.appendChild(chip);
  });
}

function addTag(tag) {
  preferredTags.add(tag);
  const input = document.getElementById("tag-search");
  input.value = "";
  input.focus();
  renderPreferredTags();
  renderSuggestions();
}

function renderSuggestions() {
  const input = document.getElementById("tag-search");
  const list = document.querySelector("[data-tag-suggestions]");
  const query = input.value.trim().toLowerCase();
  if (!query) {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    return;
  }
  const matches = allTags
    .filter((tag) => tag.toLowerCase().includes(query) && !preferredTags.has(tag))
    .slice(0, 8);
  list.innerHTML = "";
  matches.forEach((tag) => {
    const option = document.createElement("button");
    option.type = "button";
    option.role = "option";
    option.textContent = tag;
    option.addEventListener("click", () => addTag(tag));
    list.appendChild(option);
  });
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.textContent = "No matching tags";
    list.appendChild(empty);
  }
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

async function loadTagOptions() {
  const tagInput = document.getElementById("tag-search");
  try {
    const response = await fetch(`${API_BASE}/api/search/options`);
    if (!response.ok) throw new Error("Options request failed");
    const options = await response.json();
    allTags = options.tags || [];
    tagInput.disabled = !allTags.length;
    tagInput.placeholder = allTags.length ? "Start typing a tag..." : "No tags are available yet";
  } catch {
    tagInput.disabled = true;
    tagInput.placeholder = "Couldn't load tags";
  }
}

function setupTagCombobox() {
  const tagInput = document.getElementById("tag-search");
  tagInput.addEventListener("input", renderSuggestions);
  tagInput.addEventListener("focus", renderSuggestions);
  tagInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const first = document.querySelector("[data-tag-suggestions] button");
      if (first) first.click();
    }
    if (event.key === "Escape") {
      document.querySelector("[data-tag-suggestions]").hidden = true;
      tagInput.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".tag-combobox")) {
      document.querySelector("[data-tag-suggestions]").hidden = true;
      tagInput.setAttribute("aria-expanded", "false");
    }
  });
}

function setupAboutMeCounter() {
  const textarea = document.getElementById("about-me");
  const counter = document.querySelector("[data-about-me-counter]");
  const updateCounter = () => {
    counter.textContent = `${textarea.value.length}/500 characters`;
  };
  textarea.addEventListener("input", updateCounter);
  updateCounter();
}

function formatJoinDate(isoString) {
  if (!isoString) return "Unknown";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function showProfileMessage(message, isError = false) {
  const el = document.querySelector("[data-profile-message]");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("is-hidden");
  el.classList.toggle("profile-message-error", isError);
}

function clearProfileMessage() {
  const el = document.querySelector("[data-profile-message]");
  if (!el) return;
  el.textContent = "";
  el.classList.add("is-hidden");
  el.classList.remove("profile-message-error");
}

function applyAvatarPreview(profile) {
  const preview = document.querySelector("[data-avatar-preview]");
  if (!preview) return;
  preview.innerHTML = "";
  if (profile.avatar_url) {
    const img = document.createElement("img");
    img.src = profile.avatar_url;
    img.alt = "Your avatar";
    preview.appendChild(img);
  } else {
    const initial = document.createElement("span");
    initial.textContent = (profile.username || "?").charAt(0).toUpperCase();
    preview.appendChild(initial);
  }
}

async function loadProfile() {
  const usernameEl = document.querySelector("[data-profile-username]");
  const joinDateEl = document.querySelector("[data-profile-join-date]");
  const form = document.querySelector("[data-profile-form]");
  const aboutMeEl = document.getElementById("about-me");
  const counterEl = document.querySelector("[data-about-me-counter]");

  try {
    const response = await authFetch(`${API_BASE}/api/profile`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) throw new Error("Failed to load profile");

    const profile = await response.json();

    if (usernameEl) usernameEl.textContent = profile.username || "";
    if (joinDateEl) joinDateEl.textContent = formatJoinDate(profile.created_at);
    document.title = `${profile.username || "Profile"} | Axiom`;

    form.gender.value = profile.gender || "Prefer not to say";
    form.city.value = profile.city || "";
    form.country.value = profile.country || "";
    aboutMeEl.value = profile.about_me || "";
    counterEl.textContent = `${(profile.about_me || "").length}/500 characters`;

    applyAvatarPreview(profile);

    (profile.tag_preferences || []).forEach((tag) => preferredTags.add(tag));
    renderPreferredTags();
  } catch (error) {
    if (usernameEl) usernameEl.textContent = "Couldn't load";
    if (joinDateEl) joinDateEl.textContent = "Couldn't load";
    console.error("[profile.js] failed to load profile:", error);
    showProfileMessage("Couldn't load your profile. Make sure the backend is running on port 8000.", true);
  }
}

function setupProfileForm() {
  const form = document.querySelector("[data-profile-form]");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearProfileMessage();

    const button = form.querySelector('button[type="submit"]');
    const originalText = button.textContent;
    button.textContent = "Saving...";
    button.disabled = true;

    const payload = {
      gender: form.gender.value,
      city: form.city.value.trim(),
      country: form.country.value.trim(),
      about_me: document.getElementById("about-me").value.trim(),
      tag_preferences: [...preferredTags],
    };

    try {
      const response = await authFetch(`${API_BASE}/api/profile`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message =
          (typeof result.detail === "string" && result.detail) ||
          (Array.isArray(result.detail) && result.detail[0]?.msg) ||
          "Couldn't save your profile. Please try again.";
        showProfileMessage(message, true);
        return;
      }
      showProfileMessage("Profile saved.");
    } catch (error) {
      showProfileMessage("Couldn't reach the backend. Make sure it is running on port 8000.", true);
    } finally {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
}

// ---------------------------------------------------------------------
// Avatar upload + circular crop editor
// ---------------------------------------------------------------------

const AVATAR_STAGE_SIZE = 280; // the visible square editing area, in px
const AVATAR_CROP_SIZE = 220; // the circular crop guide's diameter, in px
const AVATAR_OUTPUT_SIZE = 400; // the final saved image's width/height, in px

const avatarEditorState = {
  naturalWidth: 0,
  naturalHeight: 0,
  baseScale: 1, // the "zoomed all the way out" scale that just covers the stage
  zoom: 1, // a multiplier on top of baseScale, driven by the zoom slider
  posX: 0,
  posY: 0,
};

function avatarClamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function renderAvatarEditorImage() {
  const image = document.querySelector("[data-avatar-editor-image]");
  if (!image) return;
  const scale = avatarEditorState.baseScale * avatarEditorState.zoom;
  const width = avatarEditorState.naturalWidth * scale;
  const height = avatarEditorState.naturalHeight * scale;
  image.style.width = `${width}px`;
  image.style.height = `${height}px`;
  image.style.transform = `translate(${avatarEditorState.posX}px, ${avatarEditorState.posY}px)`;
}

function clampAvatarPosition() {
  const scale = avatarEditorState.baseScale * avatarEditorState.zoom;
  const width = avatarEditorState.naturalWidth * scale;
  const height = avatarEditorState.naturalHeight * scale;
  const minX = Math.min(0, AVATAR_STAGE_SIZE - width);
  const maxX = Math.max(0, AVATAR_STAGE_SIZE - width);
  const minY = Math.min(0, AVATAR_STAGE_SIZE - height);
  const maxY = Math.max(0, AVATAR_STAGE_SIZE - height);
  avatarEditorState.posX = avatarClamp(avatarEditorState.posX, minX, maxX);
  avatarEditorState.posY = avatarClamp(avatarEditorState.posY, minY, maxY);
}

function initAvatarEditorImage(image) {
  avatarEditorState.naturalWidth = image.naturalWidth;
  avatarEditorState.naturalHeight = image.naturalHeight;
  // "Cover" scale: the smallest scale at which the image still fills the
  // whole square stage with no empty gaps, used as the 100% zoom baseline.
  avatarEditorState.baseScale = Math.max(
    AVATAR_STAGE_SIZE / image.naturalWidth,
    AVATAR_STAGE_SIZE / image.naturalHeight
  );
  avatarEditorState.zoom = 1;
  document.getElementById("avatar-zoom").value = 100;

  const width = avatarEditorState.naturalWidth * avatarEditorState.baseScale;
  const height = avatarEditorState.naturalHeight * avatarEditorState.baseScale;
  avatarEditorState.posX = (AVATAR_STAGE_SIZE - width) / 2;
  avatarEditorState.posY = (AVATAR_STAGE_SIZE - height) / 2;

  renderAvatarEditorImage();
}

function openAvatarEditor(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const image = document.querySelector("[data-avatar-editor-image]");
    image.onload = () => initAvatarEditorImage(image);
    image.src = reader.result;
    showAvatarModal();
  };
  reader.readAsDataURL(file);
}

function setupAvatarDragging() {
  const stage = document.querySelector("[data-avatar-stage]");
  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  stage.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    stage.setPointerCapture(event.pointerId);
    stage.classList.add("is-dragging");
  });

  stage.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    avatarEditorState.posX += dx;
    avatarEditorState.posY += dy;
    clampAvatarPosition();
    renderAvatarEditorImage();
  });

  const stopDragging = (event) => {
    dragging = false;
    stage.classList.remove("is-dragging");
    if (stage.hasPointerCapture(event.pointerId)) {
      stage.releasePointerCapture(event.pointerId);
    }
  };

  stage.addEventListener("pointerup", stopDragging);
  stage.addEventListener("pointercancel", stopDragging);
}

function setupAvatarZoom() {
  const slider = document.getElementById("avatar-zoom");
  slider.addEventListener("input", () => {
    avatarEditorState.zoom = Number(slider.value) / 100;
    clampAvatarPosition();
    renderAvatarEditorImage();
  });
}

function showAvatarModal() {
  const modal = document.querySelector("[data-avatar-modal]");
  modal.classList.remove("is-hidden");
  document.body.classList.add("modal-open");
}

function hideAvatarModal() {
  const modal = document.querySelector("[data-avatar-modal]");
  modal.classList.add("is-hidden");
  document.body.classList.remove("modal-open");
  const fileInput = document.querySelector("[data-avatar-file-input]");
  if (fileInput) fileInput.value = "";
}

function exportAvatarImage() {
  const image = document.querySelector("[data-avatar-editor-image]");
  const scale = avatarEditorState.baseScale * avatarEditorState.zoom;
  const cropOffset = (AVATAR_STAGE_SIZE - AVATAR_CROP_SIZE) / 2;

  // Convert the visible crop circle's position on screen back into pixel
  // coordinates on the original, full-resolution image.
  const sourceX = avatarClamp((cropOffset - avatarEditorState.posX) / scale, 0, avatarEditorState.naturalWidth);
  const sourceY = avatarClamp((cropOffset - avatarEditorState.posY) / scale, 0, avatarEditorState.naturalHeight);
  const sourceSize = Math.min(
    AVATAR_CROP_SIZE / scale,
    avatarEditorState.naturalWidth - sourceX,
    avatarEditorState.naturalHeight - sourceY
  );

  const canvas = document.createElement("canvas");
  canvas.width = AVATAR_OUTPUT_SIZE;
  canvas.height = AVATAR_OUTPUT_SIZE;
  const ctx = canvas.getContext("2d");

  // Clip to a circle before drawing, so the saved PNG is a true circle
  // with transparent corners, not just a square displayed as one.
  ctx.save();
  ctx.beginPath();
  ctx.arc(AVATAR_OUTPUT_SIZE / 2, AVATAR_OUTPUT_SIZE / 2, AVATAR_OUTPUT_SIZE / 2, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();
  ctx.drawImage(image, sourceX, sourceY, sourceSize, sourceSize, 0, 0, AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE);
  ctx.restore();

  return canvas.toDataURL("image/png");
}

async function applyAvatarEdit() {
  const applyButton = document.querySelector("[data-avatar-editor-apply]");
  const originalText = applyButton.textContent;
  applyButton.textContent = "Saving...";
  applyButton.disabled = true;

  const dataUrl = exportAvatarImage();

  try {
    const response = await authFetch(`${API_BASE}/api/profile/avatar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_data: dataUrl }),
    });
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message =
        (typeof result.detail === "string" && result.detail) ||
        "Couldn't save your avatar. Please try again.";
      hideAvatarModal();
      showProfileMessage(message, true);
      return;
    }
    applyAvatarPreview(result);
    if (window.refreshAccountAvatar) window.refreshAccountAvatar();
    hideAvatarModal();
    showProfileMessage("Avatar updated.");
  } catch (error) {
    hideAvatarModal();
    showProfileMessage("Couldn't reach the backend. Make sure it is running on port 8000.", true);
  } finally {
    applyButton.textContent = originalText;
    applyButton.disabled = false;
  }
}

function setupAvatarEditor() {
  const editButton = document.querySelector("[data-avatar-edit-button]");
  const fileInput = document.querySelector("[data-avatar-file-input]");
  const cancelButton = document.querySelector("[data-avatar-editor-cancel]");
  const closeButton = document.querySelector("[data-avatar-editor-close]");
  const applyButton = document.querySelector("[data-avatar-editor-apply]");
  const modal = document.querySelector("[data-avatar-modal]");

  if (!editButton || !fileInput || !modal) return;

  editButton.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      showProfileMessage("Please choose an image file.", true);
      fileInput.value = "";
      return;
    }
    openAvatarEditor(file);
  });

  cancelButton.addEventListener("click", hideAvatarModal);
  closeButton.addEventListener("click", hideAvatarModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) hideAvatarModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("is-hidden")) hideAvatarModal();
  });
  applyButton.addEventListener("click", applyAvatarEdit);

  setupAvatarDragging();
  setupAvatarZoom();
}

if (requireSession()) {
  setupTagCombobox();
  setupAboutMeCounter();
  setupAvatarEditor();
  loadTagOptions();
  loadProfile();
  setupProfileForm();
}