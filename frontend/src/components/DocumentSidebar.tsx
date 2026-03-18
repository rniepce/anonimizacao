import React from 'react';

interface Props {
    totalPages: number;
    currentPage: number;
    onPageChange: (page: number) => void;
}

function DocumentSidebar({ totalPages, currentPage, onPageChange }: Props) {
    const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

    return (
        <aside className="document-sidebar">
            <div className="sidebar-header">
                <h3>📄 Documentos</h3>
            </div>
            <div className="sidebar-content">
                {pages.map((page) => (
                    <div
                        key={page}
                        className={`sidebar-item ${currentPage === page ? 'active' : ''}`}
                        onClick={() => onPageChange(page)}
                    >
                        <span className="sidebar-item-icon">📃</span>
                        Página {page}
                    </div>
                ))}
            </div>
        </aside>
    );
}

export default DocumentSidebar;
