// Background Service Worker
// Gerencia downloads e comunicação com API

let API_BASE_URL = 'http://localhost:8000';

// carregar config
chrome.storage.local.get(['apiUrl'], (result) => {
    if (result.apiUrl) API_BASE_URL = result.apiUrl;
});

// Listener para mudanças na config
chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.apiUrl) {
        API_BASE_URL = changes.apiUrl.newValue;
    }
});

// Criar menu de contexto
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "anonymize-link",
        title: "Anonimizar este documento (TJMG)",
        contexts: ["link"]
    });
});

// Listener de Context Menu
chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "anonymize-link") {
        const url = info.linkUrl;
        processarUrlDocumento(url, tab.id);
    }
});

// Listener de Mensagens do Content Script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "anonymize_current_tab") {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) processarUrlDocumento(tabs[0].url, tabs[0].id);
        });
    }
    return true;
});


async function processarUrlDocumento(docUrl, tabId) {
    console.log(`Iniciando processamento para: ${docUrl}`);

    // Notificar usuário que começou
    chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: () => alert("Anonimização iniciada! Aguarde o download...")
    });

    try {
        // 1. Baixar o arquivo original (Blob)
        // Precisamos fazer fetch aqui no background para contornar alguns CORS, 
        // ou usamos a API downloads para baixar local e depois enviar? 
        // O ideal é fetch -> blob -> send to API -> get response -> download

        const response = await fetch(docUrl);
        if (!response.ok) throw new Error("Falha ao baixar documento original");
        const blob = await response.blob();

        // 2. Enviar para API de Anonimização
        const formData = new FormData();
        formData.append("file", blob, "documento_original.pdf");

        const apiEndpoint = `${API_BASE_URL}/api/anonymize`;

        const apiResponse = await fetch(apiEndpoint, {
            method: "POST",
            body: formData
        });

        if (!apiResponse.ok) throw new Error("Erro no processamento da API");

        const anonBlob = await apiResponse.blob();

        // 3. Converter para Data URL e Baixar
        const reader = new FileReader();
        reader.readAsDataURL(anonBlob);
        reader.onloadend = function () {
            const base64data = reader.result;

            chrome.downloads.download({
                url: base64data,
                filename: "documento_anonimizado_tjmg.pdf",
                saveAs: true
            });

            chrome.scripting.executeScript({
                target: { tabId: tabId },
                func: () => alert("Anonimização concluída! Verifique seus downloads.")
            });
        }

    } catch (error) {
        console.error(error);
        chrome.scripting.executeScript({
            target: { tabId: tabId },
            func: (err) => alert(`Erro: ${err}`),
            args: [error.message]
        });
    }
}
