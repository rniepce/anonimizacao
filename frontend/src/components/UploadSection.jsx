import { useRef, useState, useCallback } from 'react';

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function UploadSection({ selectedFile, onFileSelect, onRemoveFile }) {
    const fileInputRef = useRef(null);
    const [isDragOver, setIsDragOver] = useState(false);

    const handleClick = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const handleChange = useCallback(
        (e) => {
            if (e.target.files.length > 0) {
                onFileSelect(e.target.files[0]);
            }
        },
        [onFileSelect]
    );

    const handleDragOver = useCallback((e) => {
        e.preventDefault();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback(
        (e) => {
            e.preventDefault();
            setIsDragOver(false);
            if (e.dataTransfer.files.length > 0) {
                onFileSelect(e.dataTransfer.files[0]);
            }
        },
        [onFileSelect]
    );

    if (selectedFile) {
        return (
            <div className="file-info">
                <div className="file-icon">📎</div>
                <div className="file-details">
                    <span className="file-name">{selectedFile.name}</span>
                    <span className="file-size">{formatFileSize(selectedFile.size)}</span>
                </div>
                <button className="btn-remove" onClick={onRemoveFile} title="Remover arquivo">
                    ✕
                </button>
            </div>
        );
    }

    return (
        <div
            className={`upload-area${isDragOver ? ' dragover' : ''}`}
            onClick={handleClick}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <div className="upload-icon">📄</div>
            <h3>Arraste seu arquivo aqui</h3>
            <p>
                ou <span className="upload-link">clique para selecionar</span>
            </p>
            <input
                type="file"
                ref={fileInputRef}
                accept=".pdf,.docx"
                onChange={handleChange}
                hidden
            />
            <div className="upload-formats">
                <span className="format-tag">PDF</span>
                <span className="format-tag">DOCX</span>
            </div>
        </div>
    );
}

export default UploadSection;
