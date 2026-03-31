import { useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

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
            <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                className="rounded-xl p-6 flex items-center justify-between mt-6 relative overflow-hidden"
                style={{ background: 'var(--color-surface-container-low)', border: '1px solid var(--color-outline-variant)' }}
            >
                {/* Scanner line animation */}
                <motion.div
                    initial={{ scaleX: 0, opacity: 0.7 }}
                    animate={{ scaleX: 1, opacity: 0 }}
                    transition={{ duration: 0.9, ease: [0.4, 0, 0.2, 1] }}
                    style={{
                        position: 'absolute',
                        top: 0, left: 0, right: 0,
                        height: '2px',
                        background: 'linear-gradient(90deg, transparent, var(--color-accent), transparent)',
                        transformOrigin: 'left',
                    }}
                />
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="w-12 h-12 rounded-lg shadow-sm flex items-center justify-center" style={{ background: 'var(--color-surface-container-lowest)', color: 'var(--color-primary)' }}>
                            <span className="material-symbols-outlined">description</span>
                        </div>
                        {/* Green check badge */}
                        <div style={{
                            position: 'absolute', bottom: -4, right: -4,
                            width: 18, height: 18,
                            background: 'var(--color-success)',
                            borderRadius: '50%',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '2px solid var(--color-surface-container-lowest)'
                        }}>
                            <span className="material-symbols-outlined" style={{ fontSize: '11px', color: 'white' }}>check</span>
                        </div>
                    </div>
                    <div>
                        <h4 className="font-bold text-sm" style={{ color: 'var(--color-on-surface)' }}>{selectedFile.name}</h4>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="format-pill">
                                {selectedFile.type.includes('pdf') ? 'PDF' : 'DOCX'}
                            </span>
                            <span className="text-xs" style={{ color: 'var(--color-on-surface-variant)' }}>{formatFileSize(selectedFile.size)}</span>
                            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--color-outline-variant)', display: 'inline-block', margin: '0 2px' }} />
                            <span className="text-xs font-medium" style={{ color: 'var(--color-success)' }}>Pronto para análise</span>
                        </div>
                    </div>
                </div>
                <button
                    className="p-2 rounded-full transition-all flex items-center justify-center w-10 h-10 border-none cursor-pointer"
                    style={{ color: 'var(--color-on-surface-variant)', background: 'transparent' }}
                    onClick={onRemoveFile}
                    title="Remover"
                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-error)'; e.currentTarget.style.background = 'var(--color-error-container)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-on-surface-variant)'; e.currentTarget.style.background = 'transparent'; }}
                >
                    <span className="material-symbols-outlined">delete</span>
                </button>
            </motion.div>
        );
    }

    return (
        <motion.div
            animate={{
                scale: isDragOver ? 1.02 : 1,
                borderColor: isDragOver ? 'var(--color-primary)' : 'rgba(200,208,221,0.5)',
                backgroundColor: isDragOver ? 'rgba(0,53,128,0.04)' : 'var(--color-surface-container-lowest)',
            }}
            transition={{ duration: 0.2 }}
            className="rounded-xl p-8 border-2 border-dashed cursor-pointer"
            style={{ boxShadow: 'var(--shadow-ambient)' }}
            onClick={handleClick}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <div className="flex flex-col items-center justify-center py-12 text-center">
                {/* Pentagon icon shape */}
                <motion.div
                    whileHover={{ scale: 1.12, rotate: -3 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 17 }}
                    className="mb-6"
                    style={{
                        width: '80px',
                        height: '80px',
                        background: 'var(--color-accent-container)',
                        clipPath: 'polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <span className="material-symbols-outlined" style={{ fontSize: '36px', color: 'var(--color-accent)' }}>upload_file</span>
                </motion.div>
                <h3 className="text-xl font-bold font-headline mb-2" style={{ color: 'var(--color-on-surface)' }}>
                    Arraste seu arquivo aqui
                </h3>
                <p className="mb-4 text-sm max-w-sm" style={{ color: 'var(--color-on-surface-variant)' }}>
                    Tamanho máximo de 50MB por arquivo. Certifique-se de que o texto seja legível.
                </p>
                <div className="flex items-center gap-2 mb-6">
                    <span className="format-pill">PDF</span>
                    <span className="format-pill">DOCX</span>
                </div>
                <button
                    className="btn btn-secondary"
                    onClick={e => { e.stopPropagation(); handleClick(); }}
                    style={{ pointerEvents: 'auto' }}
                >
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>folder_open</span>
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
        </motion.div>
    );
}

export default UploadSection;
