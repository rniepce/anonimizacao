import { useRef, useState, useCallback } from 'react';

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

interface Props {
    selectedFile: File | null;
    onFileSelect: (file: File) => void;
    onRemoveFile: () => void;
}

function UploadSection({ selectedFile, onFileSelect, onRemoveFile }: Props) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isDragOver, setIsDragOver] = useState(false);

    const handleClick = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const handleChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            if (e.target.files && e.target.files.length > 0) {
                onFileSelect(e.target.files[0]);
            }
        },
        [onFileSelect]
    );

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
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
            <div className="bg-surface-container-low rounded-xl p-6 flex items-center justify-between mt-6">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-white rounded-lg shadow-sm flex items-center justify-center text-primary">
                        <span className="material-symbols-outlined">description</span>
                    </div>
                    <div>
                        <h4 className="font-bold text-on-surface text-sm">{selectedFile.name}</h4>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest bg-surface-container-highest px-1.5 py-0.5 rounded">
                                {selectedFile.type.includes('pdf') ? 'PDF' : 'DOCX'}
                            </span>
                            <span className="text-xs text-on-surface-variant">{formatFileSize(selectedFile.size)}</span>
                            <span className="w-1 h-1 bg-outline-variant rounded-full mx-1"></span>
                            <span className="text-xs text-emerald-600 font-medium">Pronto para análise</span>
                        </div>
                    </div>
                </div>
                <button 
                    className="p-2 text-on-surface-variant hover:text-error hover:bg-[#ffdad6] rounded-full transition-all flex items-center justify-center w-10 h-10 border-none cursor-pointer" 
                    onClick={onRemoveFile}
                    title="Remover"
                >
                    <span className="material-symbols-outlined">delete</span>
                </button>
            </div>
        );
    }

    return (
        <div
            className={`bg-surface-container-lowest rounded-xl p-8 shadow-[0_12px_40px_rgba(25,28,29,0.06)] group border-2 border-dashed ${isDragOver ? 'border-[#003f87] bg-primary/5' : 'border-outline-variant/30'} hover:border-[#003f87]/40 transition-all cursor-pointer`}
            onClick={handleClick}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-20 h-20 rounded-full bg-[#f3f4f5] flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <span className="material-symbols-outlined text-[48px] text-primary">upload_file</span>
                </div>
                <h3 className="text-xl font-bold font-headline mb-2 text-on-surface">Arraste seu arquivo PDF ou DOCX aqui</h3>
                <p className="text-on-surface-variant mb-6 text-sm max-w-sm">Tamanho máximo de 50MB por arquivo. Certifique-se de que o texto seja legível.</p>
                <button className="px-6 py-2 border border-outline-variant/40 rounded-lg text-primary font-bold text-sm bg-transparent cursor-pointer">
                    Selecionar do computador
                </button>
                <input
                    type="file"
                    ref={fileInputRef}
                    accept=".pdf,.docx"
                    onChange={handleChange}
                    hidden
                />
            </div>
        </div>
    );
}

export default UploadSection;
