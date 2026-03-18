interface Props {
    totalPages: number;
    currentPage: number;
    onPageChange: (page: number) => void;
}

function DocumentSidebar({ totalPages, currentPage, onPageChange }: Props) {
    const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

    return (
        <aside className="bg-[#f3f4f5] border-r border-[#edeeef] flex flex-col h-full p-4 gap-2 w-64 shrink-0 overflow-y-auto">
            <div className="mb-6 flex flex-col mt-2">
                <span className="text-[#191c1d] font-bold text-lg font-headline">TJMG</span>
                <span className="text-xs text-on-surface-variant font-medium tracking-wide uppercase opacity-70">Anonimizador</span>
            </div>
            
            <div className="space-y-1">
                <div className="bg-white text-[#003f87] rounded-lg shadow-sm font-bold flex items-center p-3 gap-3">
                    <span className="material-symbols-outlined">auto_stories</span>
                    Páginas
                </div>
                
                <div className="ml-4 flex flex-col gap-1 mt-2 mb-6">
                    {pages.map(page => (
                        <div
                            key={page}
                            className={`p-2 text-sm rounded-md transition-colors cursor-pointer ${
                                currentPage === page
                                    ? 'text-[#003f87] font-bold bg-white/50 border-l-4 border-[#003f87]'
                                    : 'text-[#424752] hover:bg-[#e7e8e9]'
                            }`}
                            onClick={() => onPageChange(page)}
                        >
                            Página {page}
                        </div>
                    ))}
                </div>
            </div>
        </aside>
    );
}

export default DocumentSidebar;
