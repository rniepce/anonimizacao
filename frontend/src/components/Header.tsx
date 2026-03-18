function Header() {
    return (
        <header className="bg-surface-bright flex justify-between items-center px-6 py-3 w-full border-b border-[#edeeef] z-50 shrink-0" style={{ borderBottom: '1px solid #edeeef' }}>
            <div className="flex items-center gap-8">
                <div className="text-on-surface font-extrabold text-xl font-headline tracking-tighter" style={{ letterSpacing: '-0.05em' }}>
                    TJMG Anonimizador
                </div>
                <nav className="hidden md:flex gap-6 items-center">
                    <a className="text-[#003f87] font-semibold border-b-2 border-[#003f87] font-headline tracking-tight text-lg py-1 no-underline" href="#">Resolução 615/CNJ</a>
                </nav>
            </div>
            <div className="flex items-center gap-4" style={{ display: 'flex', gap: '1rem' }}>
                <button className="material-symbols-outlined text-[#424752] bg-transparent border-none hover:bg-[#e1e3e4] p-2 rounded-full transition-colors cursor-pointer text-[24px]">help_outline</button>
                <button className="material-symbols-outlined text-[#424752] bg-transparent border-none hover:bg-[#e1e3e4] p-2 rounded-full transition-colors cursor-pointer text-[24px]">settings</button>
                <div className="w-[1px] h-8 bg-[#edeeef] mx-2" style={{ width: '1px', height: '2rem', backgroundColor: '#edeeef' }}></div>
                <button className="flex items-center gap-2 p-1 pl-3 bg-transparent border-none hover:bg-[#e1e3e4] rounded-full transition-colors cursor-pointer">
                    <span className="text-sm font-bold text-on-surface font-headline mr-2">Tribunal Admin</span>
                    <span className="material-symbols-outlined text-[32px] text-primary" style={{ fontVariationSettings: "'FILL' 1", fontSize: '32px' }}>account_circle</span>
                </button>
            </div>
        </header>
    );
}

export default Header;
