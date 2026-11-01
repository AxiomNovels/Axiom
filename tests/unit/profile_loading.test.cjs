const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../../frontend/public/user.js'), 'utf8');

test('lists load and show the owner name while the profile request is pending', async () => {
  const requests = [];
  const element = () => ({ children: [], appendChild(child) { this.children.push(child); } });
  const container = element();
  const context = {
    URLSearchParams, console, API_BASE: 'https://api.example',
    window: { location: { search: '?id=reader' } },
    document: {
      querySelector: selector => selector === '[data-user-reading-lists]' ? container : null,
      createElement: element,
    },
    authFetch: url => {
      requests.push(url);
      if (url.endsWith('/reading-lists')) return Promise.resolve({
        ok: true, json: async () => ({ username: 'Reader name', is_owner: false, lists: [] }),
      });
      return new Promise(() => {});
    },
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(requests.sort(), [
    'https://api.example/api/users/reader',
    'https://api.example/api/users/reader/reading-lists',
  ]);
  assert.equal(container.children[0].children[0].textContent,
    'Reader name does not have any public reading lists.');
});
