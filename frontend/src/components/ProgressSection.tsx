import type { ProgressInfo } from '../types';

interface Props {
    info: ProgressInfo;
}

function ProgressSection({ info }: Props) {
    return (
        <section className="bg-surface-container-lowest rounded-xl p-8 shadow-[0_12px_40px_rgba(25,28,29,0.06)] mt-6 text-center">
            <div className="flex items-center justify-center gap-4 mb-6">
                <div className="spinner" />
                <h3 className="text-xl font-bold font-headline text-on-surface">{info.title}</h3>
            </div>
            
            <div className="h-2 bg-[#edeeef] rounded-full overflow-hidden mb-4 relative w-full">
                <div
                    className="h-full bg-gradient-to-r from-[#003f87] to-[#0056b3] rounded-full transition-all duration-300 ease-in-out primary-gradient"
                    style={{ width: `${info.progress}%` }}
                />
            </div>
            
            <p className="text-sm font-medium text-on-surface-variant m-0">{info.status}</p>
        </section>
    );
}

export default ProgressSection;
