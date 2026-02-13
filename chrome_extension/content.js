// Content Script
// Injeta botão flutuante para facilitar acesso

function createFloatingButton() {
    if (document.getElementById('tjmg-anon-fab')) return; // Já existe

    const fab = document.createElement('div');
    fab.id = 'tjmg-anon-fab';
    fab.className = 'tjmg-anonymizer-fab';
    fab.title = "Anonimizar Documento Atual";

    // Ícone de Escudo (Shield)
    fab.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
      </svg>
      <div class="tjmg-anonymizer-tooltip">Anonimizar Página</div>
    `;

    fab.addEventListener('click', () => {
        // Envia mensagem para background processar a URL atual
        chrome.runtime.sendMessage({ action: "anonymize_current_tab" });

        // Feedback visual
        fab.classList.add('loading');
        setTimeout(() => fab.classList.remove('loading'), 3000);
    });

    document.body.appendChild(fab);
}

// Injetar em sites judiciais conhecidos (ou todos, conforme manifest)
// PJe, Eproc, etc.
const judicialDomains = [
    'pje', 'eproc', 'tjemg', 'trf', 'tjmg', 'jus.br'
];

const isJudicial = judicialDomains.some(d => window.location.hostname.includes(d));

// Se for site judicial OU se for um PDF aberto no navegador
if (isJudicial || window.location.href.endsWith('.pdf')) {
    createFloatingButton();
}
