"""Inbox rendering and existing actions, without servers or live accounts."""
from pathlib import Path

from playwright.sync_api import expect


INBOX_SCRIPT = Path(__file__).resolve().parents[2] / "frontend/public/inbox.js"


def test_comment_links_and_existing_inbox_actions(page):
    page.set_content('<main id="messages"></main>')
    page.evaluate("""() => {
      window.API_BASE = 'https://api.example.test';
      window.getAccessToken = () => 'test-token';
      window.requests = [];
      window.badgeRefreshes = 0;
      window.refreshInboxBadge = () => window.badgeRefreshes++;
      window.authFetch = async (url, options) => {
        window.requests.push({url, ...options});
        return {ok: true, json: async () =>
          url.endsWith('/respond') ? {status: 'accepted'} : JSON.parse(options.body || '{}')};
      };
    }""")
    page.add_script_tag(path=str(INBOX_SCRIPT))
    page.evaluate("""() => {
      const notifications = [
        {id: 'novel', type: 'comment_reply', data: {novel_id: 12}},
        {id: 'list', type: 'reading_list_comment', data: {reading_list_id: 'list&1', owner_id: 'owner?1'}},
        {id: 'nested', type: 'comment_reply', data: {reading_list_id: 'list2', owner_id: 'owner2'}},
        {id: 'missing', type: 'comment_reply', data: {}},
        {id: 'welcome', type: 'system', data: {}},
        {id: 'friend', type: 'friend_request', data: {
          friendship_id: 'friendship', friendship_status: 'pending', sender_id: 'reader', sender_username: 'Reader'
        }},
      ];
      for (const notification of notifications) {
        document.querySelector('#messages').appendChild(createNotificationCard({
          ...notification, subject: notification.id, body: '<img src=x onerror=alert(1)>',
          is_read: false, created_at: '2026-01-01T00:00:00Z'
        }));
      }
    }""")
    novel = page.locator('[data-id="novel"]')
    novel.locator('summary').click()
    expect(novel.get_by_role('link', name='View discussion')).to_have_attribute(
        'href', '/novel.html?id=12#reviews-heading'
    )
    expect(novel.get_by_role('button', name='Mark as unread')).to_be_visible()
    novel.get_by_role('button', name='Mark as unread').click()
    expect(novel).to_have_class('inbox-message is-unread')
    assert page.evaluate('window.requests.map(r => JSON.parse(r.body).is_read)') == [True, False]
    assert page.evaluate('window.badgeRefreshes') == 2
    expect(page.locator('[data-id="list"] a')).to_have_attribute(
        'href', '/shared-list.html?user=owner%3F1&id=list%261#reviews-heading'
    )
    expect(page.locator('[data-id="nested"] a')).to_have_attribute(
        'href', '/shared-list.html?user=owner2&id=list2#reviews-heading'
    )
    expect(page.locator('[data-id="missing"] a, [data-id="welcome"] a')).to_have_count(0)
    expect(page.locator('img')).to_have_count(0)  # Notification text stays escaped.

    friend = page.locator('[data-id="friend"]')
    friend.locator('summary').click()
    friend.get_by_role('button', name='Accept', exact=True).click()
    expect(friend).to_contain_text("You accepted this request. You're now friends.")
    expect(friend.get_by_role('button', name='Accept', exact=True)).to_have_count(0)
    page.once('dialog', lambda dialog: dialog.accept())
    novel.get_by_role('button', name='Delete', exact=True).click()
    expect(novel).to_have_count(0)
    assert page.evaluate('window.requests.at(-1).method') == 'DELETE'
