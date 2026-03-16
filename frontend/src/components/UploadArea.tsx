import { useRef, useState, useCallback } from 'react';

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

interface Props {
    selectedFile: File | null;
    onFileSelect: (file: File) => void;
    onFileRemove: () => void;
}

export default function UploadArea({ selectedFile, onFileSelect, onFileRemove }: Props) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [dragover, setDragover] = useState(false);

    const handleFiles = useCallback(
        (files: FileList) => {
            if (files.length === 0) return;
            const file = files[0];
            const validTypes = [
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ];
            if (!validTypes.includes(file.type) && !file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
                alert('Por favor, selecione um arquivo PDF ou DOCX.');
                return;
            }
            onFileSelect(file);
        },
        [onFileSelect]
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setDragover(false);
            handleFiles(e.dataTransfer.files);
        },
        [handleFiles]
    );

    if (selectedFile) {
        return (
            <div className="file-info" id="fileInfo">
                <div className="file-icon">📎</div>
                <div className="file-details">
                    <span className="file-name">{selectedFile.name}</span>
                    <span className="file-size">{formatFileSize(selectedFile.size)}</span>
                </div>
                <button className="btn-icon" onClick={onFileRemove} title="Remover arquivo">
                    ✕
                </button>
            </div>
        );
    }

    return (
        <div
            className={`upload-area${dragover ? ' dragover' : ''}`}
            id="uploadArea"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e: React.DragEvent) => {
                e.preventDefault();
                setDragover(true);
            }}
            onDragLeave={() => setDragover(false)}
            onDrop={handleDrop}
        >
            <div className="upload-icon">📄</div>
            <h3>Arraste seu arquivo aqui</h3>
            <p>
                ou <span className="upload-link">clique para selecionar</span>
            </p>
            <input
                ref={fileInputRef}
                type="file"
                id="fileInput"
                accept=".pdf,.docx"
                hidden
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    if (e.target.files) handleFiles(e.target.files);
                }}
            />
            <div className="upload-formats">
                <span className="format-tag">PDF</span>
                <span className="format-tag">DOCX</span>
            </div>
        </div>
    );
}
