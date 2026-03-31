interface Props {
    isDarkMode?: boolean;
    onToggleDark?: () => void;
}

function Header({ isDarkMode, onToggleDark }: Props) {
    return (
        <header
            className="flex justify-between items-center px-6 py-3 w-full shrink-0 z-50"
            style={{
                background: 'var(--color-surface-bright)',
                borderBottom: '1px solid var(--color-surface-container)',
                backdropFilter: 'blur(8px)',
                WebkitBackdropFilter: 'blur(8px)',
            }}
        >
            <div className="flex items-center gap-8">
                <div className="font-extrabold text-xl font-headline" style={{ letterSpacing: '-0.05em' }}>
                    <span style={{ color: 'var(--color-primary)' }}>TJMG</span>
                    <span style={{ color: 'var(--color-on-surface)', fontWeight: 400, margin: '0 2px' }}> </span>
                    <span style={{ color: 'var(--color-accent)', fontWeight: 800 }}>Anonimizador</span>
                </div>
                <nav className="hidden md:flex gap-6 items-center">
                    <a
                        className="font-semibold font-headline tracking-tight text-lg py-1 no-underline"
                        style={{
                            color: 'var(--color-primary)',
                            borderBottom: '2px solid var(--color-accent)',
                            paddingBottom: '2px',
                        }}
                        href="#"
                    >
                        Resolução 615/CNJ
                    </a>
                </nav>
            </div>
            <div className="flex items-center gap-3">
                <button
                    className="material-symbols-outlined bg-transparent border-none p-2 rounded-full transition-colors cursor-pointer"
                    style={{ color: 'var(--color-on-surface-variant)', fontSize: '22px' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-container)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                    help_outline
                </button>
                <button
                    className="material-symbols-outlined bg-transparent border-none p-2 rounded-full transition-colors cursor-pointer"
                    style={{ color: 'var(--color-on-surface-variant)', fontSize: '22px' }}
                    onClick={onToggleDark}
                    title={isDarkMode ? 'Modo claro' : 'Modo escuro'}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-container)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                    {isDarkMode ? 'light_mode' : 'dark_mode'}
                </button>
                <div style={{ width: '1px', height: '2rem', background: 'var(--color-surface-container)', margin: '0 0.25rem' }} />
                <button className="flex items-center gap-2 p-1 pl-3 bg-transparent border-none rounded-full transition-colors cursor-pointer"
                    style={{ color: 'var(--color-on-surface)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-container)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                    <span className="text-sm font-bold font-headline mr-1">Tribunal Admin</span>
                    <div className="header-initials-avatar">TA</div>
                </button>
            </div>
        </header>
    );
}

export default Header;
