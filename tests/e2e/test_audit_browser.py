"""Browser regressions with intercepted API responses; no real accounts."""
from test_profile_latency import profile_frontend, profile_api
from playwright.sync_api import expect


def test_search_tags_are_text_and_unknown_counts_stay_unknown(page, profile_frontend, profile_api):
    page.goto(profile_frontend + '/search.html')
    result = page.evaluate('''() => {
      const card = resultCard({id: 1, title: 'Test', tags: ['<img src=x onerror="window.injected=true">'], chapter_count: null}, 0);
      document.body.append(card);
      return {tags: card.querySelector('.result-tags').textContent,
        images: card.querySelectorAll('.result-tags img').length,
        stats: card.querySelector('.result-stats'), zero: formatCompactNumber(0), missing: formatCompactNumber(null)};
    }''')
    assert result['images'] == 0
    assert '<img' in result['tags']
    assert result['stats'] is None
    assert result['zero'] == '0' and result['missing'] is None


def test_reader_avatar_cannot_add_event_attributes(page, profile_frontend, profile_api):
    page.goto(profile_frontend + '/readers.html')
    result = page.evaluate('''() => {
      const box = document.createElement('div');
      box.innerHTML = avatarMarkup({avatar_url: 'x" onerror="window.injected=true', username: 'Test'});
      return box.querySelector('img').hasAttribute('onerror');
    }''')
    assert result is False


def test_failed_profile_load_cannot_overwrite_saved_fields(page, profile_frontend, profile_api):
    profile_api['status'] = 500
    page.goto(profile_frontend + '/profile.html')
    expect(page.locator('[data-profile-username]')).to_have_text("Couldn't load")
    expect(page.locator('[data-profile-form] button[type=submit]')).to_be_disabled()


def test_avatar_export_error_restores_save_button(page, profile_frontend, profile_api):
    page.goto(profile_frontend + '/profile.html')
    page.evaluate('''async () => {
      exportAvatarImage = () => { throw new Error('Invalid image'); };
      await applyAvatarEdit();
    }''')
    expect(page.locator('[data-avatar-editor-apply]')).to_be_enabled()


def test_refresh_outage_retains_login_and_late_reply_cannot_restore_logout(page, profile_frontend, profile_api):
    page.goto(profile_frontend + '/index.html')
    result = page.evaluate('''async () => {
      const original = window.fetch;
      storeAuthState({id:'reader'}, {access_token:'old', refresh_token:'old-refresh'}, true);
      window.fetch = async () => new Response('{}', {status:503});
      await refreshAuthSession();
      const retained = getAccessToken();
      let finish;
      window.fetch = () => new Promise(resolve => { finish = resolve; });
      const pending = refreshAuthSession();
      clearAuthState();
      finish(new Response(JSON.stringify({user:{id:'reader'}, session:{access_token:'late',refresh_token:'late'}})));
      await pending;
      window.fetch = original;
      return {retained, afterLogout:getAccessToken()};
    }''')
    assert result == {'retained': 'old', 'afterLogout': None}
