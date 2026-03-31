import { motion, AnimatePresence } from 'framer-motion';
import type { ProgressInfo } from '../types';

interface Props {
    info: ProgressInfo;
}

function ProgressSection({ info }: Props) {
    return (
        <section
            className="rounded-xl p-8 mt-6 text-center"
            style={{ background: 'var(--color-surface-container-lowest)', boxShadow: 'var(--shadow-ambient)' }}
        >
            {/* SVG Circular spinner */}
            <div className="flex flex-col items-center mb-6">
                <svg width="52" height="52" viewBox="0 0 52 52" className="mb-4" style={{ overflow: 'visible' }}>
                    {/* Track */}
                    <circle cx="26" cy="26" r="22" fill="none" stroke="var(--color-surface-container-high)" strokeWidth="4" />
                    {/* Animated arc */}
                    <motion.circle
                        cx="26" cy="26" r="22"
                        fill="none"
                        stroke="var(--color-accent)"
                        strokeWidth="4"
                        strokeLinecap="round"
                        strokeDasharray="138.2"
                        strokeDashoffset="103.6"
                        style={{ transformOrigin: '26px 26px' }}
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                    />
                </svg>
                <h3 className="text-xl font-bold font-headline" style={{ color: 'var(--color-on-surface)' }}>
                    {info.title}
                </h3>
            </div>

            {/* Progress bar */}
            <div className="h-2 rounded-full overflow-hidden mb-5 relative w-full" style={{ background: 'var(--color-surface-container-high)' }}>
                <motion.div
                    className="h-full rounded-full relative"
                    style={{ background: 'linear-gradient(90deg, var(--color-primary), var(--color-accent))' }}
                    initial={{ width: '0%' }}
                    animate={{ width: `${info.progress}%` }}
                    transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
                >
                    {/* Pulsing glow at leading edge */}
                    <motion.div
                        style={{
                            position: 'absolute',
                            right: 0, top: 0,
                            height: '100%',
                            width: '32px',
                            background: 'linear-gradient(90deg, transparent, rgba(217,119,6,0.6))',
                        }}
                        animate={{ opacity: [0.4, 1, 0.4] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                    />
                </motion.div>
            </div>

            {/* Animated status text */}
            <AnimatePresence mode="wait">
                <motion.p
                    key={info.status}
                    className="text-sm font-medium m-0"
                    style={{ color: 'var(--color-on-surface-variant)' }}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                >
                    {info.status}
                </motion.p>
            </AnimatePresence>
        </section>
    );
}

export default ProgressSection;
