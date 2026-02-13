// Popup logic to configure API URL
document.addEventListener('DOMContentLoaded', () => {
    const apiUrlInput = document.getElementById('apiUrl');
    const saveBtn = document.getElementById('saveBtn');
    const statusDiv = document.getElementById('status');

    // Load saved settings
    chrome.storage.local.get(['apiUrl'], (result) => {
        apiUrlInput.value = result.apiUrl || 'http://localhost:8000';
    });

    saveBtn.addEventListener('click', () => {
        const url = apiUrlInput.value.replace(/\/$/, ''); // Remove trailing slash
        chrome.storage.local.set({ apiUrl: url }, () => {
            statusDiv.textContent = 'Configuração salva!';
            setTimeout(() => {
                statusDiv.textContent = '';
            }, 2000);
        });
    });
});
