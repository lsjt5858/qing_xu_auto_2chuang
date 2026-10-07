const openButton = document.getElementById('open-runner');

if (!(openButton instanceof HTMLButtonElement)) throw new Error('Missing open-runner button');

openButton.addEventListener('click', async () => {
  openButton.disabled = true;
  const url = chrome.runtime.getURL('runner.html');
  const existing = (await chrome.tabs.query({})).find(tab => tab.url === url);
  if (existing?.id !== undefined) {
    await chrome.tabs.update(existing.id, { active: true });
    if (existing.windowId !== undefined) await chrome.windows.update(existing.windowId, { focused: true });
  } else {
    await chrome.tabs.create({ url, active: true });
  }
  window.close();
});
