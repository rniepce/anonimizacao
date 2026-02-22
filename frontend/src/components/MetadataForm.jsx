import { useCallback } from 'react';

function MetadataForm({ metadata, onChange }) {
    const handleChange = useCallback(
        (field) => (e) => {
            onChange((prev) => ({ ...prev, [field]: e.target.value }));
        },
        [onChange]
    );

    return (
        <div className="metadata-form">
            <h4>Metadados do Processo (Opcional)</h4>
            <div className="form-grid">
                <div className="form-group">
                    <label htmlFor="classeProcessual">Classe Processual</label>
                    <input
                        type="text"
                        id="classeProcessual"
                        placeholder="Ex: Ação Civil Pública"
                        value={metadata.classeProcessual}
                        onChange={handleChange('classeProcessual')}
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="vara">Vara</label>
                    <input
                        type="text"
                        id="vara"
                        placeholder="Ex: 1ª Vara Cível"
                        value={metadata.vara}
                        onChange={handleChange('vara')}
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="comarca">Comarca</label>
                    <input
                        type="text"
                        id="comarca"
                        placeholder="Ex: Belo Horizonte"
                        value={metadata.comarca}
                        onChange={handleChange('comarca')}
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="nerMode">Motor de Detecção</label>
                    <select
                        id="nerMode"
                        value={metadata.nerMode}
                        onChange={handleChange('nerMode')}
                    >
                        <option value="legacy">Padrão (SpaCy + Regex)</option>
                        <option value="standard">Avançado (GLiNER-PII - Lento)</option>
                        <option value="deep">Profundo (GLiNER Deep - Lento)</option>
                    </select>
                </div>
            </div>
        </div>
    );
}

export default MetadataForm;
