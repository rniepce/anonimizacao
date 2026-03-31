interface Props {
    totalPages: number;
    currentPage: number;
    onPageChange: (page: number) => void;
}

function DocumentSidebar({ totalPages, currentPage, onPageChange }: Props) {
    const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

    return (
        <aside className="w-64 shrink-0 flex flex-col h-full p-4 gap-2 overflow-y-auto" style={{ background: 'var(--color-sidebar-bg)', borderRight: 'none' }}>
            <div className="mb-6 flex flex-col mt-2" style={{ borderLeft: '3px solid var(--color-accent)', paddingLeft: '0.75rem' }}>
                <span className="font-bold text-lg font-headline" style={{ color: 'var(--color-sidebar-text)', letterSpacing: '-0.04em' }}>TJMG</span>
                <span className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--color-sidebar-text-dim)', letterSpacing: '0.08em' }}>Anonimizador</span>
            </div>

            <div className="space-y-1">
                <div className="rounded-lg shadow-sm font-bold flex items-center p-3 gap-3 text-sm" style={{ background: 'var(--color-sidebar-active)', color: 'var(--color-sidebar-text)' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>auto_stories</span>
                    Páginas
                </div>

                <div className="ml-2 flex flex-col gap-1 mt-2 mb-6">
                    {pages.map(page => (
                        <div
                            key={page}
                            className="p-2 text-sm rounded-md transition-colors cursor-pointer flex items-center gap-2"
                            style={currentPage === page ? {
                                color: '#ffffff',
                                fontWeight: 700,
                                background: 'var(--color-sidebar-active)',
                                borderLeft: '3px solid var(--color-accent)',
                                paddingLeft: '0.5rem'
                            } : {
                                color: 'var(--color-sidebar-text-dim)',
                            }}
                            onClick={() => onPageChange(page)}
                        >
                            {/* Mini A4 thumbnail */}
                            <div style={{
                                width: '18px',
                                height: '25px',
                                background: currentPage === page ? 'var(--color-accent)' : 'rgba(255,255,255,0.08)',
                                borderRadius: '2px',
                                border: '1px solid rgba(255,255,255,0.1)',
                                flexShrink: 0
                            }} />
                            Página {page}
                        </div>
                    ))}
                </div>
            </div>
        </aside>
    );
}

export default DocumentSidebar;
